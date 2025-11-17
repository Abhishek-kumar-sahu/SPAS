# Command line: python scripts/generate_report.py S001
import sys, os, io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.models import db, Student, Performance
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../database/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def generate(enrollment_no, out_path):
    with app.app_context():
        s = Student.query.filter_by(enrollment_no=enrollment_no).first()
        if not s:
            print('Student not found'); return
        perfs = Performance.query.filter_by(enrollment_no=s.id).all()
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter); p.setFont('Helvetica', 12)
        p.drawString(50,750, f'Student Performance Report - {s.name} ({s.enrollment_no})')
        y = 720
        for r in perfs:
            p.drawString(50, y, f'Subject: {r.subject} | Marks: {r.marks} | Attendance: {r.attendance} | Date: {r.date}'); y -= 20
            if y < 50: p.showPage(); y = 750
        p.showPage(); p.save(); buffer.seek(0)
        with open(out_path, 'wb') as f: f.write(buffer.getvalue())
        print('Report saved to', out_path)

if __name__ == '__main__':
    if len(sys.argv)<2: print('Usage: python scripts/generate_report.py <STUDENT_ID> [output_path]')
    else:
        sid = sys.argv[1]; out = sys.argv[2] if len(sys.argv)>=3 else f'{sid}_report.pdf'; generate(sid, out)
