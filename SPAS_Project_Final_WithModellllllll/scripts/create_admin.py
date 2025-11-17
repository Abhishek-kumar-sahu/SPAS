import os
import sys

# ✅ Fix import path so backend is accessible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import create_app
from backend.models import db, User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Check if admin already exists
    existing_admin = User.query.filter_by(username='admin').first()
    if existing_admin:
        print("⚠️ Admin user already exists.")
    else:
        admin = User(
            username='admin',
            password=generate_password_hash('majoradmin@#$1234'),
            role='Admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created successfully!")
