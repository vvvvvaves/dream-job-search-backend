from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import asyncio
import concurrent.futures
from dream_job_search import DreamJobSearch

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

class ErrorResponse(BaseModel):
    detail: str
    status_code: int

class SuccessResponse(BaseModel):
    message: str
    status: str

app = FastAPI()

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

dream_job_search = None
subscribers = []

@app.get("/logs")
async def logs():
    queue = asyncio.Queue()
    subscribers.append(queue)
    print(f"New subscriber added. Total subscribers: {len(subscribers)}")

    async def event_generator():
        try:
            while True:
                print(f"Waiting for message in queue {id(queue)}...")
                msg = await queue.get()
                print(f"Received message in queue {id(queue)}: {msg}")
                yield f"data: {msg}\n\n"
        finally:
            subscribers.remove(queue)
            print(f"Subscriber removed. Total subscribers: {len(subscribers)}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/login")
async def login():
    """
    Authenticate user and initialize the DreamJobSearch instance.
    """
    global dream_job_search
    try:
        dream_job_search = DreamJobSearch(
            client_secret_path="client_secret.json", 
            creds_path="creds.json", 
            spreadsheet_data_path="spreadsheet_data.json",
            log_subscribers=subscribers
            )
        return {"message": "Logged in successfully", "status": "success"}
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/logout")
async def logout():
    """
    Logout user and clear the DreamJobSearch instance.
    """
    global dream_job_search
    if dream_job_search is None:
        raise HTTPException(status_code=400, detail="No active session to logout from")
    dream_job_search = None
    return {"message": "Logged out successfully", "status": "success"}

@app.get("/auth/status")
async def get_auth_status():
    """
    Check the current authentication status of the user.
    """
    global dream_job_search
    if dream_job_search is None:
        raise HTTPException(status_code=401, detail="User not logged in")
    return {"message": "User is logged in", "status": "authenticated"}

@app.post("/job-postings", response_model=JobPostings)
async def get_job_postings(request: JobPostingRequest):
    """
    Get job postings based on keywords and optional location.
    Requires user to be logged in.
    """
    global dream_job_search
    if dream_job_search is None:
        raise HTTPException(status_code=401, detail="User not logged in. Please login first.")
    
    try:
        keywords = request.keywords
        location = request.location
        response = dream_job_search.find_jobs_by_keywords(keywords=keywords, location=location)
        

        
        return JobPostings(job_postings=response.to_dict(orient="records"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job search failed: {str(e)}")

@app.post("/update-database")
async def update_database(request: UpdateDatabaseRequest):
    """
    Update the job database with new locations and queries.
    Requires user to be logged in.
    """
    global dream_job_search
    if dream_job_search is None:
        raise HTTPException(status_code=401, detail="User not logged in. Please login first.")
    
    try:
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
