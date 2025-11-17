import os
import sys
from flask import Flask
from flask_cors import CORS
from flask_mail import Mail

# -------------------------------------------------------------------
# ✅ Ensure "backend" modules can be imported properly
# -------------------------------------------------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import backend modules
from backend.models import db
from backend.config import (
    SQLALCHEMY_DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS,
    SECRET_KEY
)
from backend.routes import setup_routes


mail = Mail()  # global mail instance


def create_app():
    # ---------------------------------------------------------------
    # ✅ Initialize Flask app with correct template/static paths
    # ---------------------------------------------------------------
    base_dir = os.path.abspath(os.path.dirname(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static')
    )
    CORS(app)

    # ---------------------------------------------------------------
    # ✅ Ensure data folder exists
    # ---------------------------------------------------------------
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)

    # ---------------------------------------------------------------
    # ✅ Core Configurations
    # ---------------------------------------------------------------
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

    # ---------------------------------------------------------------
    # ✅ Flask-Mail Config (for password reset)
    # ---------------------------------------------------------------
    # Predefined admin reset email
    app.config['DEFAULT_ADMIN_EMAIL'] = "abhishekkumarsahu483@gmail.com"

    # SMTP mail configuration (you can change this to any provider)
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = app.config['DEFAULT_ADMIN_EMAIL']  # same sender
    app.config['MAIL_PASSWORD'] = "vyal frti unxm wxkr"  # ⚠️ Use App Password (never real password)
    app.config['MAIL_DEFAULT_SENDER'] = ("SPAS Admin", app.config['MAIL_USERNAME'])

    # ---------------------------------------------------------------
    # ✅ Initialize Extensions
    # ---------------------------------------------------------------
    db.init_app(app)
    mail.init_app(app)

    # Register Routes (which will use 'mail' for reset)
    setup_routes(app)

    # ---------------------------------------------------------------
    # ✅ Auto-create tables
    # ---------------------------------------------------------------
    with app.app_context():
        db.create_all()
        print("✅ Database connected and initialized successfully.")

    return app


# ---------------------------------------------------------------
# ✅ Entry point
# ---------------------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
