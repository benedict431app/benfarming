import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
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
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    PERENUAL_API_KEY = os.getenv('PERENUAL_API_KEY', '')
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
    PLANTID_API_KEY = os.getenv('PLANTID_API_KEY', '')
    WEGLOT_API_KEY = os.getenv('WEGLOT_API_KEY', '')
    COHERE_API_KEY = os.getenv('COHERE_API_KEY', 'cohere-api-key-placeholder')
    
    # Email configuration
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    
    # Flask configuration
    PREFERRED_URL_SCHEME = 'https' if os.environ.get('RENDER') else 'http'
    
    # Plant disease detection
    PLANT_DISEASE_MODEL = 'plant_disease_model_v1'
