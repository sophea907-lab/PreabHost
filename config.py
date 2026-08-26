import os
from datetime import timedelta

class Config:
    SECRET_KEY = 'auracart_secret_key_12345'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads')

