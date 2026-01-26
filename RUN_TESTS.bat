@echo off
REM ============================================
REM Agentic Honeypot - All Testing Commands
REM Windows Batch File
REM ============================================

echo.
echo ============================================
echo   AGENTIC HONEYPOT - SETUP AND TEST GUIDE
echo ============================================
echo.

echo [1] SETUP COMMANDS
echo ------------------
echo.
echo # Create virtual environment:
echo python -m venv venv
echo.
echo # Activate virtual environment (Windows):
echo venv\Scripts\activate
echo.
echo # Install dependencies:
echo pip install -r requirements.txt
echo.
echo # Download spaCy model (optional):
echo python -m spacy download en_core_web_sm
echo.
echo # Configure environment:
echo copy .env.example .env
echo # Then edit .env with your API keys
echo.

echo [2] RUN SERVER
echo --------------
echo.
echo # Start API server:
echo python main.py
echo.
echo # Or with uvicorn:
echo uvicorn main:app --host 0.0.0.0 --port 8000 --reload
echo.

echo [3] RUN TESTS
echo -------------
echo.
echo # Quick demo (no server needed):
echo python demo.py
echo.
echo # API tests (server must be running):
echo python tests/test_api.py
echo.
echo # Unit tests:
echo pytest tests/test_agents.py -v
echo.
echo # All tests with pytest:
echo pytest tests/ -v
echo.

echo [4] CURL EXAMPLES
echo -----------------
echo.
echo # Health check:
echo curl -X GET "http://localhost:8000/health"
echo.
echo # Test scam detection:
echo curl -X POST "http://localhost:8000/api/v1/analyze" ^
echo   -H "Content-Type: application/json" ^
echo   -H "x-api-key: your-secret-api-key-here" ^
echo   -d "{\"sessionId\":\"test-001\",\"message\":{\"sender\":\"scammer\",\"text\":\"Your account blocked. Share OTP.\",\"timestamp\":\"2024-01-26T10:00:00Z\"},\"conversationHistory\":[],\"metadata\":{\"channel\":\"SMS\",\"language\":\"English\",\"locale\":\"IN\"}}"
echo.

echo [5] QUICK START
echo ---------------
echo.
echo Run these commands in order:
echo   1. python -m venv venv
echo   2. venv\Scripts\activate
echo   3. pip install -r requirements.txt
echo   4. copy .env.example .env
echo   5. (edit .env with your GROQ_API_KEY)
echo   6. python demo.py
echo   7. python main.py
echo.

echo ============================================
echo Done! See README.md for full documentation.
echo API docs: http://localhost:8000/docs
echo ============================================
echo.

pause
