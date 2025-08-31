# Dream Job Search Backend

## Authentication System

The backend now includes a proper authentication system with appropriate HTTP status codes for different scenarios.

### Endpoints

#### POST /login

- **Purpose**: Authenticate user and initialize the DreamJobSearch instance
- **Response**:
  - `200 OK`: Login successful
  - `500 Internal Server Error`: Login failed (e.g., invalid credentials)

#### POST /logout

- **Purpose**: Logout user and clear the DreamJobSearch instance
- **Response**:
  - `200 OK`: Logout successful
  - `400 Bad Request`: No active session to logout from

#### GET /auth/status

- **Purpose**: Check current authentication status
- **Response**:
  - `200 OK`: User is logged in
  - `401 Unauthorized`: User not logged in

#### POST /job-postings

- **Purpose**: Get job postings based on keywords and location
- **Authentication**: Required
- **Response**:
  - `200 OK`: Job postings returned successfully
  - `401 Unauthorized`: User not logged in
  - `500 Internal Server Error`: Job search failed

#### POST /update-database

- **Purpose**: Update the job database with new locations and queries
- **Authentication**: Required
- **Response**:
  - `200 OK`: Database updated successfully
  - `401 Unauthorized`: User not logged in
  - `500 Internal Server Error`: Database update failed

### HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid request (e.g., no active session for logout)
- **401 Unauthorized**: User not authenticated
- **500 Internal Server Error**: Server-side error (e.g., login failure, job search failure)

### Error Handling

All endpoints now return proper HTTP status codes and detailed error messages using FastAPI's `HTTPException`. The frontend components have been updated to handle these status codes appropriately and redirect users to login when authentication is required.

## Development Stages

First stage: console app
Second stage: desktop app (+ react native frontend + SQLite database)
Third stage: web app (+ Django + server on Azure)

## TODO

- Make sure that google API allows users to only access their own files
- Implement proper session management with JWT tokens
- Add rate limiting for API endpoints
- Implement user registration and profile management
