# Production Deployment Guide

## ✅ Production-Ready Features

### 1. **Concurrent Request Handling**
- FastAPI handles concurrent requests natively using async/await
- Multiple worker processes enable true parallelism (configure via `WORKERS` env var)
- Background tasks (intel pipeline) run independently without blocking responses
- API key rotation pool automatically distributes load across multiple keys

### 2. **Environment Configuration**
All critical values are configurable via environment variables:
- `TIMEOUT_SHORT`: Inactivity timeout for single message sessions (default: 5s)
- `TIMEOUT_LONG`: Inactivity timeout for sessions with history (default: 10s)
- `HARD_DEADLINE`: Maximum time before forced callback (default: 35s)
- `DISPATCHER_INTERVAL`: Callback dispatcher check interval (default: 1.0s)
- `WORKERS`: Number of worker processes (default: 1, use 4+ for production)
- `MAX_MESSAGE_LENGTH`: Maximum message text length (default: 10000)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30.0)

### 3. **Error Handling**
- Comprehensive try-catch blocks throughout the codebase
- Graceful degradation (fallback aggregation if Judge fails)
- Proper HTTP error responses with meaningful messages
- Request validation (empty messages, length limits)
- Detailed error logging with stack traces

### 4. **Agent Notes**
- Fixed to generate 2-3 line professional summaries
- Maximum 300 characters
- Format: Scam type → Key threats → Additional context
- Professional security summary without mentioning internal systems

### 5. **Code Cleanup**
- Removed all temporary/demo files
- Kept only one production-ready stress test file
- Debug scripts retained in `scripts/` folder for troubleshooting

### 6. **Logging**
- Structured logging with timestamps and log levels
- Rich console output for development
- Production-ready log format
- Error tracking with full stack traces

## 🚀 Deployment Steps

1. **Set Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your production values
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run in Production Mode**
   ```bash
   # Set DEBUG=false and WORKERS=4+ in .env
   python main.py
   
   # Or use uvicorn directly:
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

4. **Monitor Health**
   ```bash
   curl http://localhost:8000/health
   ```

## 📊 Performance Considerations

- **Concurrency**: FastAPI handles thousands of concurrent connections per worker
- **Background Tasks**: Intel pipeline runs asynchronously, never blocks responses
- **API Key Rotation**: Automatic load balancing across multiple API keys
- **Session Management**: In-memory with configurable timeouts
- **Callback Delivery**: Guaranteed delivery with retry logic and hard deadlines

## 🔒 Security

- API key authentication required for all requests
- Input validation (message length, content sanitization)
- Error messages don't leak internal details
- Secure API key management with rotation support

## 🧪 Testing

Run the production stress test:
```bash
python stress_test.py
```

This tests:
- Concurrent request handling
- Callback delivery
- System resilience under load
