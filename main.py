from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
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

app = FastAPI()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

dream_job_search = DreamJobSearch(creds_path="creds.json", client_secret_path="client_secret.json", spreadsheet_data_path="spreadsheet_data.json")

@app.post("/job-postings", response_model=JobPostings)
async def get_job_postings(request: JobPostingRequest):
    keywords = request.keywords
    location = request.location
    response = dream_job_search.find_jobs_by_keywords(keywords=keywords, location=location)
    return JobPostings(job_postings=response.to_dict(orient="records"))

@app.post("/update-database")
async def update_database(request: UpdateDatabaseRequest):
    locations = request.locations
    queries = request.queries
    dream_job_search.update_database(locations=locations, queries=queries)
    return {"message": "Database updated"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
