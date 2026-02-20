import asyncio
import json
import logging
from pprint import pprint

from core.orchestrator import HoneypotOrchestrator
from models.schemas import HoneypotRequest, Message, Metadata
from config.settings import get_settings

# Configure logging to see the pipeline details
logging.basicConfig(level=logging.WARNING, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

async def test_single_scenario():
    """Simulate the user's specific scenario."""
    
    settings = get_settings()
    settings.worker_pool_size = 1 # Force single worker testing
    
    # User's example text
    scammer_initial = "my phone number is +91-9876543210 and my email is scammer@fakeupi , please click on link http://fake-bank-kyc.com"
    
    session_id = "abc123-session-id"
    
    print("\n" + "="*60)
    print("🧪 Running User's Custom Test Scenario")
    print("="*60)
    
    orch = HoneypotOrchestrator()
    
    print(f"\n[Request]: Sending message to honeypot:\n'{scammer_initial}'\n")
    req = HoneypotRequest(
        sessionId=session_id,
        message=Message(sender="scammer", text=scammer_initial, timestamp=10000),
        conversationHistory=[],
        metadata=Metadata(channel="SMS", language="English", locale="IN")
    )
    res = await orch.process_message(req)
    
    print("📤 Immediate Reply JSON:")
    print(json.dumps(res.model_dump(), indent=2))
    
    print("\n⏳ Processing background intelligence (Council is voting)...")
    
    # Wait for background task to resolve and send callback
    await asyncio.sleep(12) 
    
    # ── INSPECT CALLBACK PAYLOAD ──
    session = orch.session_manager.get_session(session_id)
    print("\n" + "="*80)
    print("🕵️ EVALUATION FINAL CALLBACK PAYLOAD:")
    if session and session.final_callback_payload:
         print(json.dumps(session.final_callback_payload, indent=2))
    else:
         print("❌ No callback payload was generated.")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_single_scenario())
