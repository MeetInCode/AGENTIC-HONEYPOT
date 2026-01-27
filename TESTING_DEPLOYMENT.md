# Testing & Deployment Guide

## 1. Local Testing

Before deploying, ensure the application runs locally with the new changes.

### Start the Server
```bash
# Windows
python main.py

# OR using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Run the Simulation
We have improved the backend to persist sessions.
```bash
python simulate_honeypot.py
```
Check if `session_data/` folder is created and json files appear.

## 2. Deployment on Railway

This project is now configured for Railway deployment.

### Steps
1. Push your code to a GitHub repository.
2. Login to [Railway](https://railway.com/).
3. Click "New Project" -> "Deploy from GitHub repo".
4. Select your repository.
5. Railway will detect the `Dockerfile` and build using it.
   - We added a custom `Dockerfile` to optimize the build (using CPU-only PyTorch).
   - We also added `.dockerignore` to fix the "Build timed out" / slow upload issue.
6. **Environment Variables**: You MUST set these in Railway Settings:
   - `GROQ_API_KEY`: Your Groq API key
   - `API_SECRET_KEY`: Your chosen secret key (e.g. "honeypot-secret-123")
   - `GUVI_CALLBACK_URL`: (Optional, defaults to official URL)

### Port Configuration
The application automatically listens on the port provided by Railway (via `$PORT`).
- Default: 8000 locally
- Railway: Automatically assigned (usually 443/80 exposed via domain)

## 3. Robustness Features Added

### Session Persistence
- **Problem**: In-memory sessions are lost when the server restarts (common in cloud).
- **Solution**: We added specific logic to `SessionManager` to save/load sessions to `session_data/{id}.json`.
- **Note**: On Railway, the filesystem is ephemeral (deleted on redeploy). For true persistence across deployments, verify if you need a database (Postgres). For now, this handles process restarts/crashes robustly.

### JSON Compliance
- The API response format strictly follows the problem statement:
  ```json
  {
      "status": "success",
      "scamDetected": true,
      "extractedIntelligence": { ... },
      "engagementMetrics": { ... },
      ...
  }
  ```

### Concurrent Requests
- The server uses `uvicorn` with `async/await` throughout the pipeline.
- `DetectionCouncil` runs multiple agents in parallel using `asyncio.gather`.
- Blocking ML operations are fast enough for high throughput on text messages.
