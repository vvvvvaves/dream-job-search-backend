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

---

# Multi-User Authentication & Data Storage Implementation Guide

## Overview

This guide outlines the implementation of a proper multi-user system with JWT authentication and PostgreSQL database storage for user-specific Google API credentials and spreadsheet configurations.

## Current State Analysis

### What We Currently Have

- Global `dream_job_search` instance (not user-specific)
- Google API credentials stored in local files (`creds.json`, `token.json`)
- Basic session management using global variables
- No database for user data persistence

### What We Need to Implement

- User-specific authentication system
- Database storage for user credentials and spreadsheet configurations
- JWT-based session management
- Per-user Google API integration

## Recommended Architecture

### 1. PostgreSQL Database for Permanent Storage

- **Spreadsheet IDs and Sheet IDs**: Store permanently as configuration data
- **User profiles and preferences**: User-specific settings and search history
- **Scalability**: Handle multiple users efficiently

### 2. JWT Tokens for Authentication

- **Stateless**: No server-side session storage needed
- **User identification**: JWT payload contains user ID and basic info
- **Security**: Configurable expiration times and easy invalidation

### 3. Google API Credentials Management

- **Option A (Recommended)**: Store OAuth tokens in database
- **Option B**: Per-user OAuth flow with token storage

## Database Schema Design

### Core Tables

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User Google credentials
CREATE TABLE user_google_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expiry TIMESTAMP NOT NULL,
    scopes TEXT[], -- Store requested scopes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User spreadsheets configuration
CREATE TABLE user_spreadsheets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    spreadsheet_id VARCHAR(255) NOT NULL,
    sheet_id VARCHAR(255) NOT NULL,
    spreadsheet_name VARCHAR(255),
    sheet_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User search history (optional)
CREATE TABLE user_search_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    keywords TEXT[],
    location VARCHAR(255),
    search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Indexes for Performance

```sql
-- Performance indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_google_creds_user_id ON user_google_credentials(user_id);
CREATE INDEX idx_spreadsheets_user_id ON user_spreadsheets(user_id);
CREATE INDEX idx_search_history_user_id ON user_search_history(user_id);
```

## Implementation Steps

### Phase 1: Database Setup

1. **Install PostgreSQL dependencies**

   ```bash
   pip install psycopg2-binary sqlalchemy alembic
   ```

2. **Create database configuration**

   - Set up PostgreSQL database
   - Configure connection strings
   - Set up environment variables

3. **Implement database models**
   - Create SQLAlchemy models
   - Set up database migrations with Alembic
   - Initialize database tables

### Phase 2: Authentication System

1. **Install JWT dependencies**

   ```bash
   pip install python-jose[cryptography] passlib[bcrypt]
   ```

2. **Implement user management**

   - User registration endpoint
   - Password hashing and verification
   - User login/logout with JWT

3. **JWT token management**
   - Token generation and validation
   - Refresh token mechanism
   - Token blacklisting (optional)

### Phase 3: Google API Integration

1. **Modify Google API authentication**

   - Update `creds_and_service.py` for per-user credentials
   - Implement token refresh from database
   - Handle OAuth flow per user

2. **Spreadsheet management**
   - Store spreadsheet/sheet IDs in database
   - Implement user-specific spreadsheet operations
   - Handle multiple spreadsheets per user

### Phase 4: API Endpoint Updates

1. **Update existing endpoints**

   - Make all endpoints user-specific
   - Add JWT authentication middleware
   - Implement user context in requests

2. **Add new endpoints**
   - User profile management
   - Spreadsheet configuration management
   - Google API credential management

## Code Structure

### New Files to Create

```
backend/
├── database/
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy models
│   ├── database.py        # Database connection
│   └── migrations/        # Alembic migrations
├── auth/
│   ├── __init__.py
│   ├── jwt_handler.py     # JWT token management
│   ├── password.py        # Password hashing
│   └── dependencies.py    # FastAPI dependencies
├── schemas/
│   ├── __init__.py
│   ├── user.py            # User Pydantic models
│   └── auth.py            # Authentication models
└── services/
    ├── __init__.py
    └── user_service.py    # User business logic
```

I've created a comprehensive implementation guide that covers all the steps I recommended. This markdown document includes:

1. **Current State Analysis** - What you have vs. what you need
2. **Recommended Architecture** - Why PostgreSQL + JWT is the best approach
3. **Database Schema Design** - Complete SQL schema with indexes
4. **Implementation Steps** - 4-phase development plan
5. **Code Structure** - New files and updated files
6. **Security Considerations** - Best practices for each component
7. **Environment Variables** - Configuration setup
8. **Testing Strategy** - Comprehensive testing approach
9. **Migration Plan** - Week-by-week implementation timeline
10. **Monitoring and Maintenance** - Ongoing operational considerations
11. **Future Enhancements** - Scalability and advanced features

This guide provides a complete roadmap for implementing user-specific data storage and authentication in your Dream Job Search application. You can follow it step-by-step to build a robust multi-user system.

### Updated Files

- `main.py`: Add JWT middleware and user-specific endpoints
- `dream_job_search.py`: Make it user-specific
- `google_api/creds_and_service.py`: Support per-user credentials

## Security Considerations

### 1. Password Security

- Use bcrypt for password hashing
- Implement password complexity requirements
- Add rate limiting for login attempts

### 2. JWT Security

- Use strong secret keys
- Implement token expiration
- Consider refresh token rotation

### 3. Google API Security

- Store only OAuth tokens, never client secrets
- Implement proper token refresh
- Validate user permissions for spreadsheets

### 4. Database Security

- Use parameterized queries
- Implement proper input validation
- Add database connection pooling

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/dream_job_search
DATABASE_TEST_URL=postgresql://user:password@localhost/dream_job_search_test

# JWT
JWT_SECRET_KEY=your-super-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Google API
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

## Testing Strategy

### 1. Unit Tests

- Database models and operations
- JWT token handling
- Password hashing and verification

### 2. Integration Tests

- API endpoint authentication
- Database operations with real data
- Google API integration

### 3. End-to-End Tests

- Complete user registration flow
- Google OAuth integration
- Spreadsheet operations

## Migration Plan

### Step 1: Database Setup (Week 1)

- Set up PostgreSQL
- Create database models
- Implement basic CRUD operations

### Step 2: Authentication (Week 2)

- Implement JWT system
- Create user registration/login
- Add authentication middleware

### Step 3: Google API Integration (Week 3)

- Update Google API for multi-user
- Implement spreadsheet storage
- Test with real Google accounts

### Step 4: API Updates (Week 4)

- Update existing endpoints
- Add new user management endpoints
- Comprehensive testing

## Monitoring and Maintenance

### 1. Database Monitoring

- Connection pool health
- Query performance
- Storage usage

### 2. Authentication Monitoring

- Failed login attempts
- Token usage patterns
- User session statistics

### 3. Google API Monitoring

- API quota usage
- Token refresh success rates
- Spreadsheet operation metrics

## Future Enhancements

### 1. Advanced Features

- User roles and permissions
- API rate limiting per user
- Audit logging

### 2. Scalability

- Database sharding
- Redis caching
- Load balancing

### 3. Security

- Two-factor authentication
- OAuth providers (GitHub, Microsoft)
- Advanced threat detection

## Conclusion

This implementation will transform your single-user application into a robust, scalable multi-user platform. The combination of PostgreSQL for data persistence and JWT for authentication provides a solid foundation for growth while maintaining security and performance.

The phased approach allows for incremental development and testing, reducing risk and ensuring each component works correctly before moving to the next phase.
