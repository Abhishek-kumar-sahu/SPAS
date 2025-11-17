import os
import sys

# -------------------------------------------------------------------
# ✅ Fix import path so it works from anywhere
# -------------------------------------------------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.models import db, Student, Performance
from backend.config import SQLALCHEMY_DATABASE_URI
from flask import Flask

# -------------------------------------------------------------------
# Flask App Setup
# -------------------------------------------------------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


def init():
    """Drop and recreate all database tables."""
    with app.app_context():
        db.drop_all()
        db.create_all()

        # ✅ Optional sample data (you can remove if not needed)
        s1 = Student(student_id="S101", name="Abhishek Kumar", email="abhishek@example.com")
        s2 = Student(student_id="S102", name="Riya Sharma", email="riya@example.com")
        db.session.add_all([s1, s2])
        db.session.commit()

        print("✅ Database initialized successfully!")
        print("✅ Sample students added!")


if __name__ == "__main__":
    init()
