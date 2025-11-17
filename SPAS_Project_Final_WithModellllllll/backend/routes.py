# backend/routes.py
from flask import (
    render_template, request, redirect, url_for, jsonify,
    session, flash, current_app, Response
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import os
import pandas as pd
from sqlalchemy import func, desc
from sqlalchemy.exc import IntegrityError
import io, base64
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json

# 🔹 For email verification and password reset
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Mail, Message

# Import models
from backend.models import db, Student, Performance, User, Teacher

from backend.analytics import load_csv,train_model, predict_for_aggregated

# ------------------- CONFIG -------------------
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = ['csv', 'xlsx', 'xls', 'json'] 
    
def allowed_file(filename):
 return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

mail = Mail()
ADMIN_EMAIL = "spasdmn@gmail.com"
ADMIN_NAME = "SPAS Admin"


def setup_routes(app):
    """Setup all Flask routes"""

    # Email setup
    app.config.update(
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=ADMIN_EMAIL,
        MAIL_PASSWORD='fatj klbw qmab axle',  # Replace with your Gmail App Password
        MAIL_DEFAULT_SENDER=(ADMIN_NAME, ADMIN_EMAIL)
    )
    mail.init_app(app)
    serializer = URLSafeTimedSerializer(app.secret_key)

    # ---------------- HOME ----------------
    @app.route('/')
    def index():
        return render_template('index.html')

    # ---------------- REGISTER (STUDENT) ----------------
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            enrollment_no = request.form.get('enrollment_no')
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            department = request.form.get('department')
            semester = request.form.get('semester')
            college = request.form.get('college')

            # ---------------- VALIDATION ----------------
            if not enrollment_no or not name or not password:
                flash("Enrollment number, name, and password are required!", "danger")
                return redirect(url_for('register'))

            # Check if student already exists
            existing_student = Student.query.filter_by(enrollment_no=enrollment_no).first()
            if existing_student:
                flash("Student with this enrollment number already exists.", "warning")
                return redirect(url_for('register'))

            # ---------------- HASH PASSWORD ----------------
            hashed_password = generate_password_hash(password)

            # ---------------- ADD STUDENT ----------------
            new_student = Student(
                enrollment_no=enrollment_no,
                name=name,
                email=email,
                password=hashed_password,
                department=department,
                semester=semester,
                college=college
            )

            try:
                db.session.add(new_student)
                db.session.commit()
                flash("Student registered successfully!", "success")
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f"Error occurred: {str(e)}", "danger")
                return redirect(url_for('register'))

        # GET request
        return render_template('register.html')

    # ---------------- LOGIN ----------------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')  # Email or enrollment_no
            password = request.form.get('password')

            role = None

            # Check Admin / Teacher in User table
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                role = user.role

            # If not found, check Student table
            elif not user:
                student = Student.query.filter_by(enrollment_no=username).first()
                if student and check_password_hash(student.password, password):
                    session['user_id'] = student.enrollment_no  # primary key
                    session['username'] = student.enrollment_no
                    session['role'] = 'Student'
                    role = 'Student'

            if role:
                flash("✅ Login successful!", "success")
                # Redirect based on role
                if role == 'Admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('dashboard'))

            flash("❌ Invalid credentials!", "danger")

        return render_template('login.html')

    # ---------------- LOGOUT ----------------
    @app.route('/logout')
    def logout():
        session.clear()
        flash("👋 Logged out successfully!", "info")
        return redirect(url_for('index'))

    # ---------------- PREPARE STUDENT HISTORICAL DATA ----------------
    def prepare_student_historical_data(student, performances):
        """Prepare historical data and progress tracking for student dashboard"""
        
        if not performances:
            return {}, {}
        
        # Sort performances by date or creation order
        sorted_performances = sorted(performances, key=lambda x: x.date if hasattr(x, 'date') else x.id)
        
        # Prepare chart data
        labels = []
        actual_marks = []
        predicted_marks = []
        attendance_data = []
        dates = []
        
        for i, performance in enumerate(sorted_performances):
            test_label = f"Test {i+1}"
            labels.append(test_label)
            actual_marks.append(performance.marks)
            predicted_marks.append(getattr(performance, 'predicted_marks', performance.marks))
            attendance_data.append(performance.attendance)
            
            # Handle dates - use actual date if available, otherwise generate placeholder
            if hasattr(performance, 'date') and performance.date:
                dates.append(performance.date.strftime('%Y-%m-%d'))
            else:
                # Generate placeholder dates based on performance order
                base_date = datetime.now() - timedelta(days=len(sorted_performances) - i)
                dates.append(base_date.strftime('%Y-%m-%d'))
        
        # Calculate historical statistics
        first_test = sorted_performances[0]
        last_test = sorted_performances[-1]
        
        first_test_score = first_test.marks
        last_test_score = last_test.marks
        trend_difference = last_test_score - first_test_score
        
        if trend_difference > 0:
            trend_direction = "Improved"
            trend_class = "positive"
        elif trend_difference < 0:
            trend_direction = "Declined"
            trend_class = "negative"
        else:
            trend_direction = "Stable"
            trend_class = "neutral"
        
        # Calculate attendance trend
        first_attendance = first_test.attendance
        last_attendance = last_test.attendance
        attendance_trend = last_attendance - first_attendance
        
        if attendance_trend > 0:
            attendance_trend_direction = "Improved"
            attendance_trend_class = "positive"
        elif attendance_trend < 0:
            attendance_trend_direction = "Declined"
            attendance_trend_class = "negative"
        else:
            attendance_trend_direction = "Stable"
            attendance_trend_class = "neutral"
        
        # Calculate overall progress (average of all tests)
        overall_progress = sum(actual_marks) / len(actual_marks) if actual_marks else 0
        
        # Calculate testing period
        if dates:
            testing_period = f"{len(dates)} weeks" if len(dates) > 1 else "1 week"
        else:
            testing_period = "N/A"
        
        # Prepare student info with historical data
        student_info = {
            "first_test_date": dates[0] if dates else 'N/A',
            "last_test_date": dates[-1] if dates else 'N/A',
            "first_test_score": first_test_score,
            "last_test_score": last_test_score,
            "trend_difference": round(trend_difference, 2),
            "trend_direction": trend_direction,
            "trend_class": trend_class,
            "first_attendance": first_attendance,
            "last_attendance": last_attendance,
            "attendance_trend": round(attendance_trend, 2),
            "attendance_trend_direction": attendance_trend_direction,
            "attendance_trend_class": attendance_trend_class,
            "overall_progress": round(overall_progress, 2),
            "testing_period": testing_period
        }
        
        # Prepare chart data
        chart_data = {
            "labels": labels,
            "actual_marks": actual_marks,
            "predicted_marks": predicted_marks,
            "attendance": attendance_data,
            "dates": dates
        }
        
        return student_info, chart_data

    # ---------------- DASHBOARD (FULL ANALYTICS + SEARCH) ----------------
    @app.route('/dashboard', methods=['GET', 'POST'])
    def dashboard():
        username = session.get('username')
        role = session.get('role')

        # ---------------- CSV UPLOAD (Teacher only) ----------------
        if role == 'Teacher' and request.method == 'POST' and 'csv_file' in request.files:
            return redirect(url_for('upload'))

        # ---------------- STUDENTS DATA ----------------
        students_query = []
        student_obj = None
        
        if role == 'Teacher':
            # ✅ FIXED: Teacher lookup by email instead of teacher_id
            teacher = Teacher.query.filter_by(email=username).first()  # CHANGED: teacher_id → email
            if teacher:
                # Get teacher's college and department
                teacher_college = getattr(teacher, 'college', 'Unknown College')
                teacher_department = getattr(teacher, 'department', 'Unknown Department')
                
                students_query = Student.query.filter_by(
                    department=teacher_department, 
                    college=teacher_college
                ).all()
                
                print(f"✅ Teacher {teacher.name} viewing {len(students_query)} students from {teacher_department}, {teacher_college}")
            else:
                students_query = []
                flash("⚠️ Teacher profile not found! Please contact administrator.", "warning")
                print(f"❌ Teacher not found with email: {username}")
                
        elif role == 'Admin':
            # Admin sees all students
            students_query = Student.query.all()
        else:
            # Student sees only themselves
            student_obj = Student.query.filter_by(enrollment_no=username).first()
            students_query = [student_obj] if student_obj else []

        # Format students for template display
        students_data = []
        performance_data_list = []  # For analytics
        
        for s in students_query:
            performances = s.performances if s.performances else []
            avg_attendance = sum(p.attendance for p in performances) / len(performances) if performances else 0
            avg_marks = sum(p.marks for p in performances) / len(performances) if performances else 0
            
            # Get semester from student
            semester = getattr(s, 'semester', 'N/A')
            
            # Calculate performance status
            if avg_marks >= 75:
                performance_status = "Excellent"
                status_color = "#00ff99"
            elif avg_marks >= 60:
                performance_status = "Good"
                status_color = "#58a6ff"
            elif avg_marks >= 40:
                performance_status = "Average"
                status_color = "#ffaa00"
            else:
                performance_status = "Needs Improvement"
                status_color = "#ff4444"
            
            # Attendance status
            if avg_attendance >= 80:
                attendance_status = "Good"
                attendance_color = "#00ff99"
            elif avg_attendance >= 60:
                attendance_status = "Average"
                attendance_color = "#ffaa00"
            else:
                attendance_status = "Poor"
                attendance_color = "#ff4444"
            
            # Add to students data for display
            students_data.append({
                "enrollment": s.enrollment_no,
                "name": s.name,
                "email": s.email,
                "department": getattr(s, 'department', 'N/A'),
                "college": getattr(s, 'college', 'N/A'),
                "semester": semester,
                "avg_marks": round(avg_marks, 2),
                "avg_attendance": round(avg_attendance, 2),
                "performance_status": performance_status,
                "status_color": status_color,
                "attendance_status": attendance_status,
                "attendance_color": attendance_color,
                "total_tests": len(performances)
            })
            
            # Collect performance data for analytics
            for performance in performances:
                performance_data_list.append({
                    "enrollment_no": s.enrollment_no,
                    "name": s.name,
                    "department": getattr(s, 'department', 'N/A'),
                    "college": getattr(s, 'college', 'N/A'),
                    "subject": getattr(performance, 'subject', 'N/A'),
                    "marks": performance.marks,
                    "attendance": performance.attendance,
                    "date": getattr(performance, 'date', None),
                    "semester": semester
                })

        # Create JSON-safe version for JavaScript charts
        students_json = []
        for s in students_data:
            students_json.append({
                "enrollment": s["enrollment"],
                "name": s["name"],
                "email": s["email"],
                "department": s["department"],
                "college": s["college"],
                "semester": s["semester"],
                "avg_marks": s["avg_marks"],
                "avg_attendance": s["avg_attendance"],
                "performance_status": s["performance_status"],
                "status_color": s["status_color"],
                "attendance_status": s["attendance_status"],
                "attendance_color": s["attendance_color"],
                "total_tests": s["total_tests"]
            })

        # ---------------- TEACHERS DATA ----------------
        teachers_query = Teacher.query.all()
        teachers_data = []
        for t in teachers_query:
            if hasattr(t, 'to_dict'):
                teachers_data.append(t.to_dict())
            else:
                teachers_data.append({
                    'teacher_id': t.teacher_id,
                    'name': getattr(t, 'name', 'N/A'),
                    'email': getattr(t, 'email', 'N/A'),
                    'department': getattr(t, 'department', 'N/A'),
                    'college': getattr(t, 'college', 'N/A')
                })

        # ---------------- FILTER DATA (Admin & Teacher) ----------------
        departments = []
        colleges = []
        semesters = []
        
        # For Teacher: Only show their department and college
        if role == 'Teacher':
            teacher = Teacher.query.filter_by(email=username).first()  # CHANGED: teacher_id → email
            if teacher:
                teacher_dept = getattr(teacher, 'department', None)
                teacher_college = getattr(teacher, 'college', None)
                
                if teacher_dept and teacher_dept not in departments and teacher_dept != 'N/A':
                    departments.append(teacher_dept)
                if teacher_college and teacher_college not in colleges and teacher_college != 'N/A':
                    colleges.append(teacher_college)
        
        # For Admin: Show all departments and colleges
        elif role == 'Admin':
            for s in students_query:
                dept = getattr(s, 'department', None)
                coll = getattr(s, 'college', None)
                sem = getattr(s, 'semester', None)
                
                if dept and dept not in departments and dept != 'N/A':
                    departments.append(dept)
                if coll and coll not in colleges and coll != 'N/A':
                    colleges.append(coll)
                if sem and sem not in semesters and sem != 'N/A':
                    semesters.append(sem)
        
        # Always collect semesters from students
        for s in students_query:
            sem = getattr(s, 'semester', None)
            if sem and sem not in semesters and sem != 'N/A':
                semesters.append(sem)
        
        departments = sorted(departments)
        colleges = sorted(colleges)
        semesters = sorted(semesters)

        # ---------------- STUDENT PERFORMANCE DATA WITH HISTORICAL TRACKING ----------------
        student_info = None
        student_chart_data = None
        student_chart_json = None
        performance_history = None
        
        if role == 'Student' and students_data:
            student_info = students_data[0]
            
            current_student_obj = student_obj or Student.query.filter_by(enrollment_no=student_info['enrollment']).first()
            if current_student_obj and current_student_obj.performances:
                # Use the new historical data preparation function
                historical_info, chart_data = prepare_student_historical_data(
                    current_student_obj, 
                    current_student_obj.performances
                )
                
                # Merge historical data with existing student info
                student_info.update(historical_info)
                student_chart_data = chart_data
                
                # Prepare performance history for the table
                performance_history = []
                for i, performance in enumerate(current_student_obj.performances):
                    test_label = f"Test {i+1}"
                    
                    # Calculate progress from previous test
                    progress = 0
                    if i > 0:
                        prev_mark = current_student_obj.performances[i-1].marks
                        current_mark = performance.marks
                        progress = current_mark - prev_mark
                    
                    performance_history.append({
                        "test_name": test_label,
                        "subject": getattr(performance, 'subject', 'N/A'),
                        "semester": getattr(performance, 'semester', 'N/A'),
                        "marks": performance.marks,
                        "predicted_marks": getattr(performance, 'predicted_marks', performance.marks),
                        "attendance": performance.attendance,
                        "date": chart_data["dates"][i] if i < len(chart_data["dates"]) else 'N/A',
                        "progress": progress
                    })
                
                student_chart_json = {
                    "labels": chart_data["labels"],
                    "actual_marks": chart_data["actual_marks"],
                    "predicted_marks": chart_data["predicted_marks"],
                    "attendance": chart_data["attendance"],
                    "dates": chart_data["dates"]
                }
            else:
                # No performances - set default historical data
                student_info.update({
                    "first_test_date": 'N/A',
                    "last_test_date": 'N/A',
                    "first_test_score": 'N/A',
                    "last_test_score": 'N/A',
                    "trend_difference": 0,
                    "trend_direction": "No data",
                    "trend_class": "neutral",
                    "first_attendance": 'N/A',
                    "last_attendance": 'N/A',
                    "attendance_trend": 0,
                    "attendance_trend_direction": "No data",
                    "attendance_trend_class": "neutral",
                    "overall_progress": 0,
                    "testing_period": "N/A"
                })
                
                student_chart_data = {
                    "labels": [],
                    "actual_marks": [],
                    "predicted_marks": [],
                    "attendance": [],
                    "dates": []
                }
                student_chart_json = {
                    "labels": [],
                    "actual_marks": [],
                    "predicted_marks": [],
                    "attendance": [],
                    "dates": []
                }
                performance_history = []
        else:
            if role == 'Student':
                student_chart_json = {
                    "labels": [],
                    "actual_marks": [],
                    "predicted_marks": [],
                    "attendance": [],
                    "dates": []
                }
                performance_history = []

        # ---------------- STATISTICS DATA ----------------
        statistics = {}
        if students_data:
            all_marks = [s['avg_marks'] for s in students_data if s['avg_marks'] > 0]
            all_attendance = [s['avg_attendance'] for s in students_data if s['avg_attendance'] > 0]
            
            statistics = {
                "total_students": len(students_data),
                "average_marks": round(sum(all_marks) / len(all_marks), 2) if all_marks else 0,
                "average_attendance": round(sum(all_attendance) / len(all_attendance), 2) if all_attendance else 0,
            }
            
            if students_data:
                statistics["top_performer"] = max(students_data, key=lambda x: x['avg_marks'])
                statistics["most_consistent"] = max(students_data, key=lambda x: x['total_tests'])

        # ---------------- CHART DATA FOR ANALYTICS ----------------
        chart_data = {}
        try:
            from analytics import generate_all_chart_data
            current_student_obj_for_analytics = student_obj if role == 'Student' else None
            
            chart_data = generate_all_chart_data(
                students_data=students_data,
                student_performances=current_student_obj_for_analytics.performances if current_student_obj_for_analytics else None,
                performance_data=performance_data_list if performance_data_list else None
            )
        except Exception as e:
            print(f"Error generating chart data: {e}")
            chart_data = {}

        # ---------------- RECENT ACTIVITY DATA ----------------
        recent_activity = []
        if role in ['Admin', 'Teacher']:
            try:
                recent_students = Student.query.order_by(Student.enrollment_no.desc()).limit(5).all()
                for student in recent_students:
                    recent_activity.append({
                        "type": "new_student",
                        "message": f"New student registered: {student.name}",
                        "timestamp": "Recently"
                    })
            except Exception as e:
                print(f"Error loading recent activity: {e}")
                recent_activity = []

        # Ensure all template variables are defined with safe defaults
        template_vars = {
            'username': username or '',
            'role': role or '',
            'students': students_data or [],
            'students_json': students_json or [],
            'teachers': teachers_data or [],
            'departments': departments or [],
            'colleges': colleges or [],
            'semesters': semesters or [],
            'student_info': student_info,
            'student_chart_data': student_chart_data,
            'student_chart_json': student_chart_json or {
                "labels": [], 
                "actual_marks": [], 
                "predicted_marks": [], 
                "attendance": [],
                "dates": []
            },
            'performance_history': performance_history or [],
            'statistics': statistics or {},
            'chart_data': chart_data or {},
            'recent_activity': recent_activity or []
        }

        return render_template('dashboard.html', **template_vars)

    # ---------------- ADMIN DASHBOARD ----------------
    @app.route('/admin-dashboard')
    def admin_dashboard():
        if not session.get('user_id') or session.get('role') != 'Admin':
            flash("🚫 Access denied!", "danger")
            return redirect(url_for('dashboard'))

        stats = {
            'total_students': Student.query.count(),
            'total_teachers': Teacher.query.count(),
            'avg_marks': round(db.session.query(func.avg(Performance.marks)).scalar() or 0, 2),
            'avg_attendance': round(db.session.query(func.avg(Performance.attendance)).scalar() or 0, 2)
        }
        return render_template('admin_dashboard.html', **stats)

    # ---------------- TEACHER MANAGEMENT ----------------
    @app.route('/manage-teachers')
    def manage_teachers():
        if session.get('role') != 'Admin':
            flash("🚫 Only admins can access this page!", "danger")
            return redirect(url_for('dashboard'))
        teachers = Teacher.query.all()
        return render_template('manage_teachers.html', teachers=teachers)

    @app.route('/create-teacher', methods=['GET', 'POST'])
    def create_teacher():
        if session.get('role') != 'Admin':
            flash("🚫 Access denied!", "danger")
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            teacher_id = request.form.get('teacher_id')
            name = request.form.get('name')
            department = request.form.get('department')
            college = request.form.get('college')  # ✅ NEW FIELD
            email = request.form.get('email')
            position = request.form.get('position')
            password = request.form.get('password')
            confirm = request.form.get('confirm_password')

            # ✅ UPDATED: Include college in validation
            if not all([teacher_id, name, department, college, email, position, password, confirm]):
                flash("⚠️ All fields are required!", "warning")
                return redirect(url_for('create_teacher'))

            if password != confirm:
                flash("⚠️ Passwords do not match!", "warning")
                return redirect(url_for('create_teacher'))

            if Teacher.query.filter_by(email=email).first():
                flash("⚠️ A teacher with this email already exists!", "warning")
                return redirect(url_for('manage_teachers'))

            if Teacher.query.filter_by(teacher_id=teacher_id).first():
                flash("⚠️ Teacher ID already exists!", "warning")
                return redirect(url_for('manage_teachers'))

            hashed = generate_password_hash(password)
            
            # ✅ UPDATED: Include college field
            teacher = Teacher(
                teacher_id=teacher_id,
                name=name,
                department=department,
                college=college,  # ✅ NEW FIELD
                email=email,
                position=position
            )
            user = User(username=email, password=hashed, role='Teacher')

            try:
                db.session.add(teacher)
                db.session.add(user)
                db.session.commit()
                flash("✅ Teacher created successfully!", "success")
                return redirect(url_for('manage_teachers'))
            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error creating teacher: {str(e)}", "danger")
                return redirect(url_for('create_teacher'))

        return render_template('create_teacher.html')

    @app.route('/teachers/delete/<int:teacher_id>', methods=['POST'])
    def delete_teacher(teacher_id):
        if session.get('role') != 'Admin':
            flash("🚫 Access denied!", "danger")
            return redirect(url_for('dashboard'))

        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            flash("⚠️ Teacher not found!", "warning")
            return redirect(url_for('manage_teachers'))

        user = User.query.filter_by(username=teacher.email, role='Teacher').first()
        if user:
            db.session.delete(user)
        db.session.delete(teacher)
        db.session.commit()
        flash("✅ Teacher deleted successfully!", "success")
        return redirect(url_for('manage_teachers'))

    # ---------------- DELETE STUDENT (Admin + Teacher) ----------------
    @app.route('/students/delete/<student_id>', methods=['POST'])
    def delete_student(student_id):
        """
        Admin: can delete any student  
        Teacher: can delete only students from their own department  
        """

        role = session.get('role')
        if role not in ('Admin', 'Teacher'):
            flash("🚫 Access denied!", "danger")
            return redirect(url_for('dashboard'))

        # Fetch student based on enrollment number
        student = Student.query.filter_by(enrollment_no=student_id).first()

        if not student:
            flash("⚠️ Student not found!", "warning")
            return redirect(url_for('dashboard'))

        # ---------------------------
        # TEACHER RESTRICTION (By Department)
        # ---------------------------
        if role == 'Teacher':
            teacher = Teacher.query.filter_by(email=session.get('username')).first()  # CHANGED: Use email lookup

            if not teacher:
                flash("⚠️ Teacher record missing!", "warning")
                return redirect(url_for('dashboard'))

            # Compare department of teacher and student
            if teacher.department != student.department:
                flash("🚫 You can delete only students from your department!", "danger")
                return redirect(url_for('dashboard'))

        # ---------------------------
        # DELETE ALL RELATED DATA
        # ---------------------------
        Performance.query.filter_by(student_enrollment_no=student.enrollment_no).delete()

        user = User.query.filter_by(username=student.email, role='Student').first()
        if user:
            db.session.delete(user)

        db.session.delete(student)
        db.session.commit()

        flash("✅ Student deleted successfully!", "success")
        return redirect(url_for('dashboard'))

    # ---------------- UPLOAD DATA (MULTI-FILE PREVIEW + IMPORT) ----------------
    @app.route('/upload', methods=['GET', 'POST'])
    def upload():
        # ✅ FIXED: Allow both Admin and Teacher roles
        if session.get('role') not in ['Admin', 'Teacher']:  # CHANGED: Fixed condition
            flash("🚫 Access denied!", "danger")
            return redirect(url_for('dashboard'))

        previews = []

        if request.method == 'POST':
            uploaded_files = request.files.getlist('files')
            if not uploaded_files or uploaded_files == [None]:
                flash("⚠️ No files selected!", "danger")
                return redirect(request.url)

            parsed_frames = []
            success_count = 0

            for file in uploaded_files:
                filename = secure_filename(file.filename)
                if filename == "":
                    continue

                if not allowed_file(filename):
                    previews.append({'filename': filename, 'error': 'Invalid file type!'})
                    continue

                try:
                    ext = filename.rsplit('.', 1)[1].lower()
                    if ext == 'csv':
                        df = pd.read_csv(file)
                    elif ext in ['xlsx', 'xls']:
                        df = pd.read_excel(file)
                    elif ext == 'json':
                        df = pd.read_json(file)

                    # ✅ FIX: Normalize column names (handle different naming conventions)
                    df.columns = df.columns.str.strip().str.lower()
                    column_mapping = {
                        'enrollment': 'enrollment_no',
                        'enrollno': 'enrollment_no',
                        'studentid': 'enrollment_no',
                        'student_id': 'enrollment_no',
                        'avg marks': 'marks',
                        'avg_marks': 'marks',
                        'average marks': 'marks',
                        'avg attendance': 'attendance',
                        'avg_attendance': 'attendance',
                        'average attendance': 'attendance',
                        'date': 'date',
                        'test_date': 'date',
                        'exam_date': 'date'
                    }
                    df.rename(columns=column_mapping, inplace=True)

                    parsed_frames.append((filename, df))

                    previews.append({
                        'filename': filename,
                        'head_html': df.head(5).to_html(classes="preview-table", index=False),
                        'rows': len(df)
                    })

                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.seek(0)
                    file.save(file_path)

                except Exception as e:
                    previews.append({'filename': filename, 'error': str(e)})
                    continue

            # Import all parsed files into DB with duplicate handling
            any_error = False
            
            for filename, df in parsed_frames:
                try:
                    file_success_count = 0
                    for _, row in df.iterrows():
                        # ✅ FIX: Handle different column names for enrollment_no
                        enrollment_no = None
                        for col in ['enrollment_no', 'enrollment', 'enrollno', 'studentid']:
                            if col in row and pd.notna(row[col]):
                                enrollment_no = str(row[col]).strip()
                                break
                        
                        if not enrollment_no:
                            continue

                        # ✅ FIX: Check for required fields with flexible column names
                        name = row.get('name') or row.get('student_name') or 'Unknown'
                        department = row.get('department') or row.get('dept') or 'General'
                        college = row.get('college') or row.get('college_name') or 'Unknown College'
                        semester = str(row.get('semester') or '1')

                        if not all([enrollment_no, name, department, college, semester]):
                            continue

                        # Update existing student or create new
                        student = Student.query.filter_by(enrollment_no=enrollment_no).first()
                        if student:
                            student.name = name
                            student.email = row.get('email', student.email)
                            student.department = department
                            student.semester = semester
                            student.college = college
                        else:
                            # Hash the password properly
                            from werkzeug.security import generate_password_hash
                            hashed_password = generate_password_hash('default123')
                            
                            student = Student(
                                enrollment_no=enrollment_no,
                                name=name,
                                email=row.get('email', ''),
                                password=hashed_password,
                                department=department,
                                semester=semester,
                                college=college
                            )
                            db.session.add(student)
                        
                        db.session.flush()

                        # ✅ FIX: Handle performance data - check if subject data exists
                        subject_name = row.get('subject', 'General')
                        marks_value = row.get('marks', 0)
                        attendance_value = row.get('attendance', 0)
                        
                        # ✅ NEW: Handle date field for historical tracking
                        date_value = row.get('date')
                        if date_value and pd.notna(date_value):
                            try:
                                # Try to parse the date
                                if isinstance(date_value, str):
                                    date_value = datetime.strptime(date_value, '%Y-%m-%d').date()
                                else:
                                    # Handle Excel serial dates
                                    date_value = date_value.date() if hasattr(date_value, 'date') else datetime.now().date()
                            except:
                                date_value = datetime.now().date()
                        else:
                            date_value = datetime.now().date()

                        # Safe conversion for marks and attendance
                        try:
                            marks_value = float(marks_value) if pd.notna(marks_value) else 0.0
                        except (ValueError, TypeError):
                            marks_value = 0.0
                        
                        try:
                            attendance_value = float(attendance_value) if pd.notna(attendance_value) else 0.0
                        except (ValueError, TypeError):
                            attendance_value = 0.0

                        # Only create performance record if we have valid data
                        if subject_name and (marks_value > 0 or attendance_value > 0):
                            perf = Performance.query.filter_by(
                                student_enrollment_no=student.enrollment_no, 
                                subject=subject_name,
                                date=date_value
                            ).first()
                            
                            if perf:
                                perf.marks = marks_value
                                perf.attendance = attendance_value
                                perf.date = date_value
                            else:
                                perf = Performance(
                                    student_enrollment_no=student.enrollment_no,
                                    subject=subject_name,
                                    marks=marks_value,
                                    attendance=attendance_value,
                                    date=date_value  # ✅ NEW: Store date for historical tracking
                                )
                                db.session.add(perf)

                        file_success_count += 1

                    db.session.commit()
                    success_count += file_success_count

                except Exception as e:
                    db.session.rollback()
                    any_error = True
                    previews.append({'filename': filename, 'error': str(e)})

            # Model retraining (keep your existing fixed code here)
            model_trained = False
            mse_value = 0.0
            
            try:
                # Your existing model training code
                student_count = Student.query.count()
                performance_count = Performance.query.count()
                
                if student_count > 0 and performance_count > 0:
                    from sqlalchemy import text
                    query = text("""
                        SELECT s.enrollment_no, s.department, s.semester, s.college, 
                            p.subject, p.marks, p.attendance, p.date
                        FROM students s
                        JOIN performances p ON s.enrollment_no = p.student_enrollment_no
                    """)
                    
                    students_df = pd.read_sql(query, db.session.bind)
                    
                    if not students_df.empty and len(students_df) >= 5:
                        model, mse_value = train_model(students_df)
                        model_trained = True
                        flash(f"✅ Model retrained successfully! MSE: {mse_value:.4f}", "success")
                    else:
                        flash("ℹ️ Not enough data for model retraining (minimum 5 records required)", "info")
                else:
                    flash("ℹ️ Not enough student or performance data for model retraining", "info")
                    
            except Exception as e:
                flash(f"⚠️ Model retraining failed: {str(e)}", "warning")

            # Success messages
            if any_error:
                flash("⚠️ Some files failed to import. See previews for details.", "warning")
            else:
                if success_count > 0:
                    if model_trained:
                        flash(f"✅ {success_count} records processed successfully! Model retrained with MSE: {mse_value:.4f}", "success")
                    else:
                        flash(f"✅ {success_count} records processed successfully!", "success")
                else:
                    flash("⚠️ No valid data found in uploaded files. Please check if files contain required columns.", "warning")

            return render_template("upload.html", previews=previews)

        return render_template("upload.html", previews=previews)

    # ---------------- SERVER-SIDE CSV EXPORT FOR STUDENTS ----------------
    @app.route('/export/students.csv')
    def export_students_csv():
        try:
            # Authentication check
            if not session.get('user_id'):
                return redirect(url_for('login'))
            if session.get('role') not in ('Admin', 'Teacher'):
                flash("🚫 Access denied!", "danger")
                return redirect(url_for('dashboard'))

            # Get search query
            q = request.args.get('q', '').strip()
            students_q = Student.query
            
            # Apply search filter if provided
            if q:
                students_q = students_q.filter(
                    (Student.name.ilike(f'%{q}%')) |
                    (Student.enrollment_no.ilike(f'%{q}%')) |
                    (Student.email.ilike(f'%{q}%')) |
                    (Student.college.ilike(f'%{q}%')) |  # ✅ Added college search
                    (Student.department.ilike(f'%{q}%'))  # ✅ Added department search
                )
            
            students = students_q.all()

            rows = []
            for student in students:
                perfs = Performance.query.filter_by(student_enrollment_no=student.enrollment_no).all()
                
                # Calculate averages safely
                if perfs:
                    try:
                        marks = round(sum(p.marks for p in perfs) / len(perfs), 2)
                        attendance = round(sum(p.attendance for p in perfs) / len(perfs), 2)
                    except (ZeroDivisionError, TypeError):
                        marks = 0.0
                        attendance = 0.0
                else:
                    marks = 0.0
                    attendance = 0.0
                
                # ✅ FIXED: Added all missing fields from Student model
                rows.append({
                    'enrollment_no': student.enrollment_no,
                    'name': student.name,
                    'email': student.email or '',
                    'college': student.college or '',  # ✅ Added college field
                    'department': student.department or '',  # ✅ Added department field
                    'semester': student.semester or '',  # ✅ Added semester field
                    'avg_marks': marks,
                    'avg_attendance': attendance,
                    'performance_records_count': len(perfs)  # ✅ Added count for context
                })

            # ✅ FIXED: Updated columns to include all fields
            df = pd.DataFrame(rows, columns=[
                'enrollment_no', 
                'name', 
                'email', 
                'college',  # ✅ Added
                'department',  # ✅ Added
                'semester',  # ✅ Added
                'avg_marks', 
                'avg_attendance',
                'performance_records_count'  # ✅ Added
            ])
            
            csv_data = df.to_csv(index=False)
            
            # ✅ FIXED: Add timestamp to filename to avoid caching issues
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"students_export_{timestamp}.csv"
            
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={"Content-disposition": f"attachment; filename={filename}"}
            )
        
        except Exception as e:
            # ✅ FIXED: Added error handling
            flash(f"❌ Error exporting CSV: {str(e)}", "danger")
            return redirect(url_for('manage_students'))

   

    # ---------------- FORGET PASSWORD ROUTES ----------------

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        """Forget password - send reset link to email"""
        if request.method == 'POST':
            email = request.form.get('email')
            
            if not email:
                flash("⚠️ Please enter your email address!", "warning")
                return redirect(url_for('forgot_password'))
            
            # Check in all user tables - UPDATED: Search by appropriate fields
            user = None
            user_type = None
            user_email = None  # Store the actual email to send to
            
            # Check in User table (Admin/Teacher) - search by username or email if exists
            user_obj = User.query.filter_by(username=email).first()
            if not user_obj:
                # If User model has email field, try that
                if hasattr(User, 'email'):
                    user_obj = User.query.filter_by(email=email).first()
            
            if user_obj:
                user = user_obj
                user_type = getattr(user_obj, 'role', 'User')
                # Determine what email to use for the token and email sending
                if hasattr(user_obj, 'email') and user_obj.email:
                    user_email = user_obj.email
                else:
                    # If no email field, use the input email (username might be email)
                    user_email = email
            
            # Check in Student table (assuming Student has email field)
            if not user:
                student = Student.query.filter_by(email=email).first()
                if student:
                    user = student
                    user_type = 'Student'
                    user_email = student.email
            
            if not user:
                flash("❌ No account found with this email address!", "danger")
                return redirect(url_for('forgot_password'))
            
            if not user_email:
                flash("❌ No email address associated with this account!", "danger")
                return redirect(url_for('forgot_password'))
            
            try:
                # Generate reset token (10 minutes expiration)
                # Use user_email for the token since Student uses email
                token = serializer.dumps(user_email, salt='password-reset-salt')
                reset_url = url_for('reset_password', token=token, _external=True)
                
                # Send email (your existing email code)
                msg = Message(
                    subject="🔐 Password Reset Request - Student Performance Analysis System",
                    recipients=[user_email],
                    sender=("SPAS Admin", ADMIN_EMAIL)
                )
                
                msg.body = f"""
    Hello,

    You have requested to reset your password for the Student Performance Analysis System.

    Click the link below to reset your password:
    {reset_url}

    ⚠️ This link will expire in 10 minutes.

    If you didn't request this reset, please ignore this email.

    Best regards,
    SPAS Team
    """
                
                # Your HTML email template (keep your existing one)
                msg.html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .button {{ display: inline-block; padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 10px; border-radius: 5px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
                <p>Student Performance Analysis System</p>
            </div>
            <div class="content">
                <h2>Hello,</h2>
                <p>You have requested to reset your password for your SPAS account.</p>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong> This reset link will expire in <strong>10 minutes</strong>.
                </div>
                
                <p>Click the button below to reset your password:</p>
                <div style="text-align: center;">
                    <a href="{reset_url}" class="button">Reset Your Password</a>
                </div>
                
                <p>If the button doesn't work, copy and paste this link in your browser:</p>
                <p style="word-break: break-all; background: #eee; padding: 10px; border-radius: 5px; font-size: 12px;">{reset_url}</p>
                
                <p>If you didn't request this reset, please ignore this email.</p>
                <p>Best regards,<br><strong>SPAS Team</strong></p>
            </div>
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
                
                mail.send(msg)
                flash("✅ Password reset link has been sent to your email! The link expires in 10 minutes.", "success")
                return redirect(url_for('forgot_password'))
                
            except Exception as e:
                flash(f"❌ Error sending email: {str(e)}", "danger")
                return redirect(url_for('forgot_password'))
        
        # GET request - show the forget password form
        return render_template('forgot_password.html')
    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        """Reset password with token - 10 minute expiration"""
        try:
            # 10 minutes = 600 seconds
            email_from_token = serializer.loads(token, salt='password-reset-salt', max_age=600)
        except SignatureExpired:
            flash("❌ Password reset link has expired. Please request a new one.", "danger")
            return redirect(url_for('forgot_password'))
        except BadSignature:
            flash("❌ Invalid reset link. Please request a new one.", "danger")
            return redirect(url_for('forgot_password'))
        
        # Token is valid - pass token_valid to template
        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if not password or not confirm_password:
                flash("⚠️ Please fill in all fields!", "warning")
                return render_template('reset_password.html', token_valid=True, token=token)
            
            if password != confirm_password:
                flash("⚠️ Passwords do not match!", "warning")
                return render_template('reset_password.html', token_valid=True, token=token)
            
            if len(password) < 6:
                flash("⚠️ Password must be at least 6 characters long!", "warning")
                return render_template('reset_password.html', token_valid=True, token=token)
            
            try:
                # Update password in appropriate table
                user_updated = False
                
                # Check User table (Admin/Teacher) - search by username or email
                user = User.query.filter_by(username=email_from_token).first()
                if not user and hasattr(User, 'email'):
                    user = User.query.filter_by(email=email_from_token).first()
                
                if user:
                    user.password = generate_password_hash(password)
                    user_updated = True
                
                # Check Student table
                if not user_updated:
                    student = Student.query.filter_by(email=email_from_token).first()
                    if student:
                        student.password = generate_password_hash(password)
                        user_updated = True
                
                if user_updated:
                    db.session.commit()
                    flash("✅ Password has been reset successfully! You can now login with your new password.", "success")
                    return redirect(url_for('login'))
                else:
                    flash("❌ User not found. Please request a new reset link.", "danger")
                    return redirect(url_for('forgot_password'))
                    
            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error resetting password: {str(e)}", "danger")
                return render_template('reset_password.html', token_valid=True, token=token)
        
        # GET request - pass token_valid to template
        return render_template('reset_password.html', token_valid=True, token=token)

    # ---------------- ACCESS CONTROL ----------------
    @app.before_request
    def restrict_access():
        public = ['/', '/login', '/register', '/forgot-password', '/reset-password']
        if not any(request.path.startswith(p) for p in public):
            if not session.get('user_id'):
                flash("⚠️ Please log in first!", "warning")
                return redirect(url_for('login'))

    # end setup_routes