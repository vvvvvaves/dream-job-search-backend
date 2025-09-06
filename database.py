import os
import json
import bcrypt
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, DateTime, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from contextlib import contextmanager

load_dotenv()

# SQLAlchemy setup
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    email = Column(String(255), primary_key=True)
    google_creds = Column(JSON, nullable=False)
    spreadsheet_data = Column(JSON, nullable=False)
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<User(email='{self.email}')>"

class DreamJobSearchDatabase:
    def __init__(self):
        # Create engine with connection pooling
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(
            database_url,
            pool_size=10,           # Number of connections to maintain
            max_overflow=20,        # Additional connections when pool is full
            pool_timeout=30,        # Seconds to wait for connection
            pool_recycle=3600,      # Recycle connections after 1 hour
            pool_pre_ping=True,     # Validate connections before use
            echo=False              # Set to True for SQL debugging
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create tables
        self.create_tables()
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def create_tables(self):
        """Create all tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
        except SQLAlchemyError as e:
            print(f"Error creating tables: {e}")
            raise
    
    def hash_password(self, plain_password: str) -> str:
        """Hash a password for storing in database"""
        salt_rounds = int(os.getenv("SALT_ROUNDS", "12"))  # Default to 12 if not set
        salt = bcrypt.gensalt(salt_rounds)
        return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, plain_password: str, stored_hash: str) -> bool:
        """Verify password using bcrypt"""
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), stored_hash.encode('utf-8'))
        except Exception:
            return False
    
    def register_user(self, email: str, google_creds: dict, spreadsheet_data: dict, password: str) -> bool:
        """Register a new user"""
        try:
            with self.get_session() as session:
                # Check if user already exists
                existing_user = session.query(User).filter(User.email == email).first()
                if existing_user:
                    return False
                
                # Hash the password
                password_hash = self.hash_password(password)
                
                # Create new user
                new_user = User(
                    email=email,
                    google_creds=google_creds,
                    spreadsheet_data=spreadsheet_data,
                    password_hash=password_hash
                )
                
                session.add(new_user)
                print(f"New user added to database: {new_user}")
                return True
                
        except SQLAlchemyError as e:
            print(f"Error registering user: {e}")
            return False
    
    def get_user(self, email: str) -> dict:
        """Get user by email"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.email == email).first()
                if user:
                    return {
                        'email': user.email,
                        'google_creds': user.google_creds,
                        'spreadsheet_data': user.spreadsheet_data,
                        'created_at': user.created_at,
                        'updated_at': user.updated_at
                    }
                return None
                
        except SQLAlchemyError as e:
            print(f"Error getting user: {e}")
            return None
    
    def get_user_creds(self, email: str) -> dict:
        """Get user credentials by email"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.email == email).first()
                return {"google_creds": user.google_creds, "spreadsheet_data": user.spreadsheet_data} if user else {}
                
        except SQLAlchemyError as e:
            print(f"Error getting user creds: {e}")
            return {}
    
    def update_user(self, email: str, google_creds: dict, spreadsheet_data: dict) -> bool:
        """Update user credentials"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.email == email).first()
                if user:
                    user.google_creds = google_creds
                    user.spreadsheet_data = spreadsheet_data
                    user.updated_at = datetime.utcnow()
                    return True
                return False
                
        except SQLAlchemyError as e:
            print(f"Error updating user: {e}")
            return False
    
    def update_user_password(self, email: str, new_password: str) -> bool:
        """Update user password"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.email == email).first()
                if user:
                    user.google_creds['password_hash'] = self.hash_password(new_password)
                    user.updated_at = datetime.utcnow()
                    return True
                return False
                
        except SQLAlchemyError as e:
            print(f"Error updating password: {e}")
            return False
    
    def authenticate_user(self, email: str, password: str) -> dict:
        """Authenticate user with email and password"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.email == email).first()
                if user and user.password_hash:
                    if self.verify_password(password, user.password_hash):
                        return {
                            'email': user.email,
                            'google_creds': user.google_creds,
                            'spreadsheet_data': user.spreadsheet_data,
                            'created_at': user.created_at,
                            'updated_at': user.updated_at
                        }
                return None
        except SQLAlchemyError as e:
            print(f"Error authenticating user: {e}")
            return None
            
    
    def delete_user(self, email: str) -> bool:
        """Delete user by email"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.email == email).first()
                if user:
                    session.delete(user)
                    return True
                return False
                
        except SQLAlchemyError as e:
            print(f"Error deleting user: {e}")
            return False
    
    def list_users(self, limit: int = 100) -> list:
        """List all users (for admin purposes)"""
        try:
            with self.get_session() as session:
                users = session.query(User).limit(limit).all()
                return [
                    {
                        'email': user.email,
                        'created_at': user.created_at,
                        'updated_at': user.updated_at
                    }
                    for user in users
                ]
                
        except SQLAlchemyError as e:
            print(f"Error listing users: {e}")
            return []
    
    def health_check(self) -> bool:
        """Check database connection health"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False
    
    def close(self):
        """Close database connections"""
        try:
            self.engine.dispose()
        except Exception as e:
            print(f"Error closing database: {e}")

# Example usage and testing
if __name__ == "__main__":
    try:
        # Initialize database
        db = DreamJobSearchDatabase()
        
        # Health check
        if not db.health_check():
            print("Database connection failed!")
            exit(1)
        
        print("Database connected successfully!")
        
        # Test user registration
        test_email = "test@example.com"
        test_password = "secure_password123"
        test_creds = {
            "google_tokens": {"access_token": "fake_token"},
            "linkedin_session": {"session_id": "fake_session"}
        }
        test_spreadsheet_data = {
            "spreadsheet_id": "fake_spreadsheet_id",
            "spreadsheet_name": "fake_spreadsheet_name"
        }
        # Register user
        success = db.register_user(test_email, test_creds, test_spreadsheet_data, test_password)
        print(f"User registered: {success}")
        
        # Authenticate user
        authenticated_user = db.authenticate_user(test_email, test_password)
        print(f"Authentication successful: {authenticated_user is not None}")
        
        # Get user credentials (without password hash)
        creds = db.get_user_data(test_email)
        print(f"User credentials: {creds}")
        
        # Clean up test user
        db.delete_user(test_email)
        print("Test user cleaned up")
        
    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        if 'db' in locals():
            db.close()