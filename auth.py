# backend/auth.py
from database import DreamJobSearchDatabase
import jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()

class AuthService:
    def __init__(self):
        self.db = DreamJobSearchDatabase()
        self.jwt_secret = os.getenv("JWT_SECRET_KEY")
    
    def register(self, email, password, google_creds, spreadsheet_data):
        # Uses SQLAlchemy session internally
        success = self.db.register_user(email, google_creds, spreadsheet_data, password)
        if success:
            return self.create_jwt_token(email)
        return None
    
    def login(self, email, password):
        # Uses SQLAlchemy session internally
        user = self.db.authenticate_user(email, password)
        if user:
            return self.create_jwt_token(email)
        return None
    
    def create_jwt_token(self, email):
        payload = {
            'email': email,
            'exp': datetime.utcnow() + timedelta(days=1),
            'iat': datetime.utcnow()
        }
        jwt_algorithm = os.getenv("JWT_ALGORITHM")
        return jwt.encode(payload, self.jwt_secret, algorithm=jwt_algorithm)
    
    def verify_jwt_token(self, token):
        try:
            jwt_algorithm = os.getenv("JWT_ALGORITHM")
            payload = jwt.decode(token, self.jwt_secret, algorithms=[jwt_algorithm])
            return payload['email']
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None