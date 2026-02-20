import asyncio
import json
import logging
import time

from core.orchestrator import HoneypotOrchestrator
from models.schemas import HoneypotRequest, Message, Metadata
from config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

payload = {
  "sessionId": "uuid-v4-string",
  "message": {
    "sender": "scammer",
    "text": "URGENT: Your account has been compromised. my phone number is +91-9876543210 and my email is scammer@fakeupi , please click on link http://fake-bank-kyc.com",
    "timestamp": "2025-02-11T10:30:00Z"
  },
  "conversationHistory": [
    {
      "sender": "scammer",
      "text": "Previous message...",
      "timestamp": 1700000000000
    },
    {
      "sender": "user",
      "text": "Your previous response...",
      "timestamp": 1700000005000
    },
    {
      "sender": "user",
      "text": "your case id is CS-12334444",
      "timestamp": 1700000008000
    }
  ],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}

async def run_test():
    # Override callback URL to point to our temp server
    settings = get_settings()
    settings.guvi_callback_url = "http://127.0.0.1:8111/callback"
    
    orch = HoneypotOrchestrator()
    
    # Send the request
    print("\n" + "="*80)
    print("🚀 Sending custom payload from user to HoneypotOrchestrator")
    print("="*80 + "\n")
    
    req = HoneypotRequest(**payload)
    
    # 1. Immediate Reply
    res = await orch.process_message(req)
    
    print("📤 Immediate Reply JSON:")
    print(json.dumps(res.model_dump(), indent=2))
    
    print("\n⏳ Processing background intelligence (Sending callback to temp server in a moment)...")
    await asyncio.sleep(15) 
    
    # Verify our system state
    session = orch.session_manager.get_session("uuid-v4-string")
    if session and session.callback_sent:
        print("\n✅ Callback marked as sent correctly inside session.")
    else:
        print("\n❌ Callback NOT marked as sent inside session.")

if __name__ == "__main__":
    asyncio.run(run_test())
