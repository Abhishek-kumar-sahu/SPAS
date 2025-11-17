from backend.models import db, User
from backend.config import SQLALCHEMY_DATABASE_URI
from flask import Flask
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
db.init_app(app)

def seed():
    with app.app_context():
        db.create_all()

        users = [
            User(username="admin", password=generate_password_hash("admin123"), role="Admin"),
            
        ]

        db.session.bulk_save_objects(users)
        db.session.commit()
        print("✅ Seeded users successfully!")

if __name__ == "__main__":
    seed()
