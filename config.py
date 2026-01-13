import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

class Config:
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production'))
    
    # Database - Use PostgreSQL on Render, SQLite locally
    if os.environ.get('RENDER'):
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    else:
        DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
    
    # Ensure upload folder exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # API Keys
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    PERENUAL_API_KEY = os.getenv('PERENUAL_API_KEY')
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
    PLANTID_API_KEY = os.getenv('PLANTID_API_KEY')
    WEGLOT_API_KEY = os.getenv('WEGLOT_API_KEY')
    COHERE_API_KEY = os.getenv('COHERE_API_KEY')
    
    # Flask configuration
    PREFERRED_URL_SCHEME = 'https' if os.environ.get('RENDER') else 'http'
    
    # Session configuration
    SESSION_COOKIE_SECURE = True if os.environ.get('RENDER') else False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_SECURE = True if os.environ.get('RENDER') else False
    REMEMBER_COOKIE_HTTPONLY = True
    
    # M-Pesa settings (for Kenya)
    MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY', '')
    MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET', '')
    MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE', '')
    MPESA_PASSKEY = os.getenv('MPESA_PASSKEY', '')
    
    # Email settings
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', MAIL_USERNAME)
    
    # Site settings
    SITE_NAME = 'AgriConnect'
    SITE_DESCRIPTION = 'Connecting Farmers and Agrovets'
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@agriconnect.com')
