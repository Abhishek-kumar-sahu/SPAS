from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ------------------ STUDENT MODEL ------------------
class Student(db.Model):
    __tablename__ = 'students'

    enrollment_no = db.Column(db.String(50), primary_key=True)  # primary key
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)       # hashed password
    department = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.String(10), nullable=False)
    college = db.Column(db.String(150), nullable=False)

    performances = db.relationship(
        'Performance',
        backref='student',
        cascade='all, delete-orphan',
        lazy=True
    )

    def __repr__(self):
        return f"<Student {self.name} ({self.enrollment_no})>"

# ------------------ PERFORMANCE MODEL ------------------
class Performance(db.Model):
    __tablename__ = 'performances'

    id = db.Column(db.Integer, primary_key=True)
    student_enrollment_no = db.Column(
        db.String(50), db.ForeignKey('students.enrollment_no'), nullable=False
    )
    subject = db.Column(db.String(100), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    attendance = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)

    def __repr__(self):
        return f"<Performance {self.subject} - {self.marks}>"

# ------------------ USER MODEL ------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role
        }

# ------------------ TEACHER MODEL ------------------
class Teacher(db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    college = db.Column(db.String(100))  # ✅ CORRECTED: db.Column and db.String
    email = db.Column(db.String(120), unique=True, nullable=False)
    position = db.Column(db.String(50))

    def to_dict(self):
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'name': self.name,
            'department': self.department,
            'college': self.college,
            'email': self.email,
            'position': self.position
        }
