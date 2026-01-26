#!/usr/bin/env bash
# ============================================
# Agentic Honeypot - All Testing Commands
# ============================================
# This script contains all commands needed to
# set up, run, and test the Agentic Honeypot.
# Run commands individually as needed.
# ============================================

echo "🍯 Agentic Honeypot - Test Commands Reference"
echo "=============================================="

# ============================================
# 1. SETUP COMMANDS
# ============================================

# Create and activate virtual environment
# python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# Install dependencies
# pip install -r requirements.txt

# Download spaCy model (optional)
# python -m spacy download en_core_web_sm

# Copy and configure environment
# cp .env.example .env
# Then edit .env with your API keys

# ============================================
# 2. RUN SERVER
# ============================================

# Start the API server (development mode)
# python main.py

# Or with uvicorn for more control
# uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production mode (no reload)
# uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# ============================================
# 3. RUN TESTS
# ============================================

# Run API integration tests (requires server running)
# python tests/test_api.py

# Run unit tests with pytest
# pytest tests/test_agents.py -v

# Run all tests with coverage
# pytest tests/ -v --cov=. --cov-report=html

# ============================================
# 4. CURL COMMANDS FOR TESTING
# ============================================

echo ""
echo "📡 Sample cURL commands:"
echo ""

# Health check
echo "# Health Check:"
echo 'curl -X GET "http://localhost:8000/health"'
echo ""

# Analyze a scam message
echo "# Analyze Scam Message:"
cat << 'EOF'
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key-here" \
  -d '{
    "sessionId": "test-session-001",
    "message": {
      "sender": "scammer",
      "text": "Your SBI account will be blocked today. Verify immediately by sharing OTP.",
      "timestamp": "2024-01-26T10:00:00Z"
    },
    "conversationHistory": [],
    "metadata": {
      "channel": "SMS",
      "language": "English",
      "locale": "IN"
    }
  }'
EOF
echo ""

# Follow-up message in same session
echo "# Follow-up Message (Multi-turn):"
cat << 'EOF'
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key-here" \
  -d '{
    "sessionId": "test-session-001",
    "message": {
      "sender": "scammer",
      "text": "Share your UPI PIN to verify. Send to scammer@ybl",
      "timestamp": "2024-01-26T10:01:00Z"
    },
    "conversationHistory": [
      {
        "sender": "scammer",
        "text": "Your SBI account will be blocked today. Verify immediately by sharing OTP.",
        "timestamp": "2024-01-26T10:00:00Z"
      },
      {
        "sender": "user",
        "text": "What should I do?",
        "timestamp": "2024-01-26T10:00:30Z"
      }
    ],
    "metadata": {
      "channel": "SMS",
      "language": "English",
      "locale": "IN"
    }
  }'
EOF
echo ""

# List active sessions
echo "# List Sessions:"
echo 'curl -X GET "http://localhost:8000/api/v1/sessions" -H "x-api-key: your-secret-api-key-here"'
echo ""

# Get session details
echo "# Get Session Details:"
echo 'curl -X GET "http://localhost:8000/api/v1/session/test-session-001" -H "x-api-key: your-secret-api-key-here"'
echo ""

# Force callback
echo "# Force Callback:"
echo 'curl -X POST "http://localhost:8000/api/v1/callback/test-session-001" -H "x-api-key: your-secret-api-key-here"'
echo ""

# ============================================
# 5. PYTHON TEST SNIPPETS
# ============================================

echo "🐍 Python Test Snippets:"
echo ""

cat << 'EOF'
# Quick Python test
import asyncio
import httpx

async def test_honeypot():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/analyze",
            json={
                "sessionId": "py-test-001",
                "message": {
                    "sender": "scammer",
                    "text": "URGENT: Your account blocked. Share OTP now!",
                    "timestamp": "2024-01-26T10:00:00Z"
                },
                "conversationHistory": [],
                "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
            },
            headers={"x-api-key": "your-secret-api-key-here"}
        )
        print(response.json())

asyncio.run(test_honeypot())
EOF

echo ""
echo "=============================================="
echo "📖 For full documentation, see README.md"
echo "📖 API docs available at http://localhost:8000/docs"
echo "=============================================="
