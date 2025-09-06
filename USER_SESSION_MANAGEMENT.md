# User Session Management for DreamJobSearch

This document explains how user-specific `DreamJobSearch` instances are managed in the application.

## Current Implementation: In-Memory Sessions

### How It Works:

1. **User Login**: Creates JWT token + initializes DreamJobSearch instance
2. **Session Storage**: Each user gets their own entry in `user_sessions` dict
3. **Instance Reuse**: Same DreamJobSearch instance is reused for all user requests
4. **Cleanup**: Session is cleared on logout

### Data Structure:

```python
user_sessions = {
    "user1@example.com": {
        "dream_job_search": DreamJobSearchInstance,
        "subscribers": [queue1, queue2, ...]  # For real-time logs
    },
    "user2@example.com": {
        "dream_job_search": DreamJobSearchInstance,
        "subscribers": [queue3, ...]
    }
}
```

### API Flow:

```
1. POST /login
   ↓
   Create JWT token + Initialize DreamJobSearch instance

2. Any protected endpoint (job-postings, update-database)
   ↓
   Get user's existing DreamJobSearch OR initialize if missing

3. POST /logout
   ↓
   Clean up user session from memory
```

### Pros:

- ✅ Fast access (in-memory)
- ✅ User isolation
- ✅ Automatic initialization
- ✅ Real-time logs per user

### Cons:

- ❌ Lost on server restart
- ❌ Memory usage grows with users
- ❌ Single-server only (no load balancing)

## Alternative Approaches:

### Option 2: Database-Backed Sessions

```python
# Store session metadata in database
class UserSession(Base):
    __tablename__ = 'user_sessions'

    email = Column(String, primary_key=True)
    session_data = Column(JSON)  # DreamJobSearch config
    created_at = Column(DateTime)
    last_accessed = Column(DateTime)

# Recreate DreamJobSearch on each request
async def get_dream_job_search(email: str):
    session = db.get_user_session(email)
    return DreamJobSearch(**session.session_data)
```

**Pros**: Persistent, scalable
**Cons**: Slower (database + recreation overhead)

### Option 3: Redis Cache

```python
import redis
import pickle

redis_client = redis.Redis()

async def store_user_session(email: str, dream_job_search: DreamJobSearch):
    # Serialize and store in Redis
    data = pickle.dumps(dream_job_search)
    redis_client.setex(f"session:{email}", 3600, data)  # 1 hour TTL

async def get_user_session(email: str):
    data = redis_client.get(f"session:{email}")
    return pickle.loads(data) if data else None
```

**Pros**: Fast, persistent, scalable
**Cons**: Additional infrastructure, serialization complexity

### Option 4: Lazy Initialization

```python
# Don't store instances, recreate on demand
async def get_dream_job_search(email: str):
    user_creds = db.get_user_creds(email)
    return DreamJobSearch(
        client_secret_path="client_secret.json",
        creds_path=user_creds['google_creds_path'],
        spreadsheet_data_path=user_creds['spreadsheet_data_path']
    )
```

**Pros**: No memory leaks, stateless
**Cons**: Initialization overhead per request

## Recommendations:

### For Development/Small Scale:

- **Current in-memory approach** is perfect
- Simple, fast, easy to debug

### For Production/Scale:

- **Option 3 (Redis)** for best performance with persistence
- **Option 4 (Lazy)** for simplicity and stateless architecture
- **Option 2 (Database)** for budget-conscious setups

## Monitoring & Debugging:

### Check Active Sessions:

```python
@app.get("/admin/sessions")
async def get_active_sessions():
    return {
        "active_users": list(user_sessions.keys()),
        "total_sessions": len(user_sessions),
        "memory_usage": f"{len(str(user_sessions))} chars"
    }
```

### Session Cleanup (Memory Management):

```python
import asyncio
from datetime import datetime, timedelta

async def cleanup_old_sessions():
    """Clean up sessions older than 2 hours"""
    while True:
        current_time = datetime.now()
        for email in list(user_sessions.keys()):
            # Add timestamp tracking to sessions
            # Remove if too old
            pass
        await asyncio.sleep(3600)  # Check every hour

# Start cleanup task
asyncio.create_task(cleanup_old_sessions())
```

## Security Considerations:

1. **Memory Leaks**: Implement session cleanup
2. **Resource Limits**: Limit max concurrent sessions
3. **Isolation**: Each user's DreamJobSearch is isolated
4. **Credentials**: User credentials stored securely in database
