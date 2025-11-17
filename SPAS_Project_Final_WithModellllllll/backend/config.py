import os

# Base directory (backend/)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Create a /database folder if it doesn't exist
DB_DIR = os.path.join(BASE_DIR, '..', 'database')
os.makedirs(DB_DIR, exist_ok=True)

# SQLite database path (absolute)
SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(DB_DIR, 'app.db')}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Optional: secret key for session handling
SECRET_KEY = "spas_secret_key_2025"
