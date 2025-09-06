from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import asyncio
import concurrent.futures
from dream_job_search import DreamJobSearch
from auth import AuthService
from typing import Optional
import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Verify critical environment variables on startup
def verify_env():
    """Verify that required environment variables are set"""
    google_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not google_secret:
        print("WARNING: GOOGLE_CLIENT_SECRET not found in environment")
    else:
        print("✓ GOOGLE_CLIENT_SECRET loaded successfully")
    
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    if not jwt_secret:
        print("WARNING: JWT_SECRET_KEY not found in environment")
    else:
        print("✓ JWT_SECRET_KEY loaded successfully")

verify_env()

class JobPosting(BaseModel):
    score: int
    matched_keywords: str
    link: str
    job_title: str
    job_company: str
    job_location: str

class JobPostings(BaseModel):
    job_postings: list[JobPosting]

class JobPostingRequest(BaseModel):
    keywords: list[str]
    location: str | None = None

class UpdateDatabaseRequest(BaseModel):
    locations: list[str]
    queries: list[str]

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    other_creds: dict = {}

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class GoogleOAuthRequest(BaseModel):
    code: str
    state: str = None

class ErrorResponse(BaseModel):
    detail: str
    status_code: int

class SuccessResponse(BaseModel):
    message: str
    status: str

app = FastAPI()

# JWT Security scheme
security = HTTPBearer()
auth_service = AuthService()

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store user-specific instances and subscribers
user_sessions = {}  # {email: {"dream_job_search": instance, "subscribers": []}}
global_subscribers = []

# Dependency to verify JWT token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and verify JWT token from Authorization header"""
    token = credentials.credentials
    email = auth_service.verify_jwt_token(token)
    
    if email is None:
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return email

async def get_user_session(email: str):
    """Get or create user session"""
    if email not in user_sessions:
        user_sessions[email] = {
            "dream_job_search": None,
            "subscribers": []
        }
    return user_sessions[email]

async def initialize_user_dream_job_search(email: str):
    """Initialize DreamJobSearch for a specific user"""
    try:
        session = await get_user_session(email)
        if session["dream_job_search"] is not None:
            return session["dream_job_search"]  # Already initialized
        
        # Get user's Google credentials from database
        user_creds = auth_service.db.get_user_creds(email)
        
        # Initialize DreamJobSearch with user's credentials
        # Extract the actual credential data
        google_creds = user_creds.get('google_creds', {})
        spreadsheet_data = user_creds.get('spreadsheet_data', {})
        
        # Get Google client secret from environment
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        dream_job_search = DreamJobSearch(
            creds=google_creds,  # Pass the actual Google tokens
            client_secret=client_secret,  # Pass the client secret JSON
            spreadsheet_data=spreadsheet_data,  # Pass the spreadsheet data
            log_subscribers=session["subscribers"]
        )
        
        session["dream_job_search"] = dream_job_search
        return dream_job_search
        
    except Exception as e:
        print(f"Error initializing DreamJobSearch for {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize services: {str(e)}")

async def get_current_user_from_query(token: str = None):
    """Alternative auth method for EventSource (query parameter)"""
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    
    email = auth_service.verify_jwt_token(token)
    if email is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return email

@app.get("/logs")
async def logs(token: str = None, current_user: str = Depends(get_current_user_from_query)):
    """Get logs for the authenticated user"""
    session = await get_user_session(current_user)
    queue = asyncio.Queue()
    session["subscribers"].append(queue)
    print(f"New subscriber added for {current_user}. Total subscribers: {len(session['subscribers'])}")

    async def event_generator():
        try:
            while True:
                print(f"Waiting for message in queue {id(queue)} for {current_user}...")
                msg = await queue.get()
                print(f"Received message in queue {id(queue)} for {current_user}: {msg}")
                yield f"data: {msg}\n\n"
        finally:
            session["subscribers"].remove(queue)
            print(f"Subscriber removed for {current_user}. Total subscribers: {len(session['subscribers'])}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# PUBLIC ENDPOINTS (No authentication required)
@app.post("/api/auth/google/callback")
async def google_oauth_callback(request: GoogleOAuthRequest):
    """Handle Google OAuth callback and exchange code for tokens"""
    try:
        print(f"OAuth callback received: code={request.code[:10]}..., state={request.state}")
        
        # Get Google client secret from environment
        client_secret_json = os.getenv("GOOGLE_CLIENT_SECRET")
        if not client_secret_json:
            print("ERROR: GOOGLE_CLIENT_SECRET environment variable not set")
            raise HTTPException(status_code=500, detail="Google client secret not configured")
        
        print("GOOGLE_CLIENT_SECRET found, parsing...")
        client_secret = json.loads(client_secret_json)
        google_config = client_secret["installed"]
        
        # Exchange authorization code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            'client_id': google_config['client_id'],
            'client_secret': google_config['client_secret'],
            'code': request.code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'http://localhost:5173/auth/google/callback'  # Must match frontend
        }
        
        print(f"Making token exchange request to Google with client_id: {google_config['client_id']}")
        response = requests.post(token_url, data=data)
        print(f"Google response status: {response.status_code}")
        
        if not response.ok:
            error_text = response.text
            print(f"Google token exchange failed: {error_text}")
            try:
                error_data = response.json()
                error_type = error_data.get('error', 'unknown_error')
                error_desc = error_data.get('error_description', 'Unknown error')
                
                # Provide user-friendly error messages
                if error_type == 'invalid_grant':
                    user_message = "The authorization code has expired or been used already. Please try the registration process again."
                elif error_type == 'invalid_client':
                    user_message = "OAuth client configuration error. Please contact support."
                elif error_type == 'invalid_request':
                    user_message = "Invalid OAuth request. Please try again."
                else:
                    user_message = f"Google authentication failed: {error_desc}"
                    
                raise HTTPException(
                    status_code=400, 
                    detail=user_message
                )
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Token exchange failed with status {response.status_code}"
                )
        else:
            print("Google token exchange successful")
        
        tokens = response.json()
        
        return {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "scope": tokens.get("scope"),
            "token_type": tokens.get("token_type", "Bearer")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")

@app.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Register a new user"""
    try:
        print(f"Registration request received for email: {request.email}")
        print(f"Other creds keys: {list(request.other_creds.keys())}")
        
        # Extract Google credentials and spreadsheet data from other_creds
        google_creds = request.other_creds.get('google_creds', {})
        spreadsheet_data = request.other_creds.get('spreadsheet_data', {})
        
        print(f"Google creds received: {bool(google_creds)}")
        if google_creds:
            print(f"Google creds keys: {list(google_creds.keys())}")
        
        token = auth_service.register(request.email, request.password, google_creds, spreadsheet_data)
        if token:
            return TokenResponse(access_token=token)
        raise HTTPException(status_code=400, detail="Registration failed - user may already exist")
    except Exception as e:
        print(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login and get JWT token"""
    token = auth_service.login(request.email, request.password)
    if token:
        # Initialize user's DreamJobSearch instance on login
        try:
            await initialize_user_dream_job_search(request.email)
            print(f"DreamJobSearch initialized for user: {request.email}")
        except Exception as e:
            print(f"Warning: Could not initialize DreamJobSearch for {request.email}: {str(e)}")
            # Still return token even if DreamJobSearch fails - user can retry later
        
        return TokenResponse(access_token=token)
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/logout")
async def logout(current_user: str = Depends(get_current_user)):
    """
    Logout user and clear the DreamJobSearch instance.
    Note: With JWT, logout is handled client-side by discarding the token.
    """
    # Clean up user session
    if current_user in user_sessions:
        session = user_sessions[current_user]
        # Clean up any resources if needed
        if session["dream_job_search"]:
            # Close any connections, cleanup resources
            pass
        del user_sessions[current_user]
        print(f"Cleaned up session for user: {current_user}")
    
    return {"message": f"User {current_user} logged out successfully", "status": "success"}

# PROTECTED ENDPOINTS (JWT token required)
@app.get("/auth/status")
async def get_auth_status(current_user: str = Depends(get_current_user)):
    """Check authentication status (requires valid JWT)"""
    session = await get_user_session(current_user)
    dream_job_search_initialized = session["dream_job_search"] is not None
    
    return {
        "message": f"User {current_user} is authenticated", 
        "status": "authenticated",
        "dream_job_search_initialized": dream_job_search_initialized
    }

@app.post("/initialize-services")
async def initialize_services(current_user: str = Depends(get_current_user)):
    """Manually initialize or reinitialize DreamJobSearch services for the user"""
    try:
        # Force reinitialize by clearing existing instance
        session = await get_user_session(current_user)
        session["dream_job_search"] = None
        
        # Initialize fresh instance
        dream_job_search = await initialize_user_dream_job_search(current_user)
        
        return {
            "message": f"Services initialized successfully for {current_user}", 
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service initialization failed: {str(e)}")

@app.post("/job-postings", response_model=JobPostings)
async def get_job_postings(
    request: JobPostingRequest, 
    current_user: str = Depends(get_current_user)
):
    """
    Get job postings based on keywords and optional location.
    Requires authentication.
    """
    try:
        # Get user's DreamJobSearch instance
        dream_job_search = await initialize_user_dream_job_search(current_user)
        
        print(f"User {current_user} is searching for jobs")
        keywords = request.keywords
        location = request.location
        response = dream_job_search.find_jobs_by_keywords(keywords=keywords, location=location)
        
        return JobPostings(job_postings=response.to_dict(orient="records"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job search failed: {str(e)}")

@app.post("/update-database")
async def update_database(
    request: UpdateDatabaseRequest,
    current_user: str = Depends(get_current_user)
):
    """
    Update the job database with new locations and queries.
    Requires authentication.
    """
    try:
        # Get user's DreamJobSearch instance
        dream_job_search = await initialize_user_dream_job_search(current_user)
        
        print(f"User {current_user} is updating database")
        locations = request.locations
        queries = request.queries
        # Run the database update in a separate thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            await loop.run_in_executor(
                executor, 
                dream_job_search.update_database, 
                locations, 
                queries
            )
        
        return {"message": "Database updated successfully", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)