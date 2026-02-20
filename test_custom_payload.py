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
  "sessionId": "demo-session-all-intel-001",
  "message": {
    "sender": "scammer",
    "text": "URGENT: Your SBI account ending 1234 has been blocked due to suspicious UPI activity. Call us on +91-9876543210 or verify now at http://fake-bank-kyc.com using case ID CASE-REF-2026-001.",
    "timestamp": "2025-02-11T10:30:00Z"
  },
  "conversationHistory": [
    {
      "sender": "scammer",
      "text": "Dear customer, this is SBI Security Team. We noticed multiple failed login attempts on your net banking linked to card 1234-5678-9012-3456 and policy number POLICY-FAKE-445566.",
      "timestamp": 1739265600000
    },
    {
      "sender": "user",
      "text": "What exactly happened and how do I fix this?",
      "timestamp": 1739265660000
    },
    {
      "sender": "scammer",
      "text": "To avoid permanent block, pay a small verification fee via UPI to scammer.fraud@fakebank and share the OTP you receive on your registered email scammer@fake.com.",
      "timestamp": 1739265720000
    },
    {
      "sender": "user",
      "text": "Why do I need to pay any fee? SBI never asks this on SMS.",
      "timestamp": 1739265780000
    },
    {
      "sender": "scammer",
      "text": "This is a special security audit linked to order ORDER-FAKE-2026-0001 for your recent online purchase. Confirm your bank account 1234567890123456 and policy number ULIP-FAKE-991122 under ticket TICKET-FAKE-7788.",
      "timestamp": 1739265840000
    },
    {
      "sender": "user",
      "text": "If this is official, why are you asking for full account and policy details on SMS instead of the SBI app?",
      "timestamp": 1739265900000
    }
  ],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN",
    "scenarioType": "bank_fraud_upi_phishing_combo",
    "testCaseId": "SCENARIO-ALL-INTEL-001"
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
