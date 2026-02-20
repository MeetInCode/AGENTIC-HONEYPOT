import asyncio
import json
import logging
from pprint import pprint

from core.orchestrator import HoneypotOrchestrator
from models.schemas import HoneypotRequest, Message, Metadata
from services.intelligence_extractor import IntelligenceExtractor
from config.settings import get_settings

# Configure logging to see the pipeline details
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

async def test_evaluation_pipeline():
    """Simulate the exact payload an evaluator will send with the new fields."""
    
    settings = get_settings()
    settings.worker_pool_size = 1 # Force single worker testing
    
    # 1. Provide an elaborate scam encompassing multiple new intelligence fields
    scammer_initial = "URGENT from HDFC Bank: Your Policy #POL-55091 has a pending payment. If not verified, your Order #ORD-99-B will be cancelled. Immediate action required to Case ID CC-019-B!"
    scammer_followup = "Please click http://hdfc-verify-kyc.com/update and send 10 rs to secure.verify@hdfc or email us at support@hdfc-verify-kyc.com. Contact +91-9876543210 for help."
    
    session_id = "test-eval-556677"
    
    print("\n" + "="*60)
    print("🧪 Starting Honeypot Evaluation Crosscheck Test")
    print("="*60)
    
    orch = HoneypotOrchestrator()
    
    # ── FIRST REQUEST ──
    print("\n[Request 1]: First connection from evaluator...")
    req1 = HoneypotRequest(
        sessionId=session_id,
        message=Message(sender="scammer", text=scammer_initial, timestamp=10000),
        conversationHistory=[],
        metadata=Metadata(channel="SMS", language="English", locale="IN")
    )
    res1 = await orch.process_message(req1)
    
    await asyncio.sleep(4) # Let intel run in background (since it's the first message, wait > 3s council delay)
    
    # ── SECOND REQUEST ──
    print(f"\n[Request 2]: Follow-up connection, replying to AI: '{res1.reply}'...")
    req2 = HoneypotRequest(
        sessionId=session_id,
        message=Message(sender="scammer", text=scammer_followup, timestamp=20000),
        conversationHistory=[
            {"sender": "scammer", "text": scammer_initial},
            {"sender": "user", "text": res1.reply}
        ],
        metadata=Metadata(channel="SMS", language="English", locale="IN")
    )
    res2 = await orch.process_message(req2)
    
    await asyncio.sleep(10) # Wait for LLMs to generate intelligence and process the HTTP callback
    
    # ── INSPECT CALLBACK PAYLOAD ──
    session = orch.session_manager.get_session(session_id)
    print("\n" + "="*60)
    print("🕵️ EVALUATION FINAL CALLBACK PAYLOAD:")
    if session.final_callback_payload:
         print(json.dumps(session.final_callback_payload, indent=2))
    else:
         print("❌ No callback payload was generated. Are keys correctly set?")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_evaluation_pipeline())
