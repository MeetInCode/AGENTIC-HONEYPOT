import asyncio
import json
import logging
from pprint import pprint
import time

from core.orchestrator import HoneypotOrchestrator
from models.schemas import HoneypotRequest, Message, Metadata
from config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s | %(levelname)-8s | %(message)s")

scenarios = [
    {
        "id": "scenario-1-bank-kyc",
        "description": "Bank KYC Phishing",
        "text": "Dear Customer, your HDFC bank account will be suspended today. Please complete your KYC immediately by clicking http://kyc-update-hdfc.in. For help call +91-9876543210."
    },
    {
        "id": "scenario-2-upi-fraud",
        "description": "UPI Money Request",
        "text": "Cashback of Rs.1999 is approved. Enter your UPI PIN to receive money in your bank account linked to 8765432109@ybl. Urgent!"
    },

]

async def run_scenarios():
    settings = get_settings()
    settings.worker_pool_size = 5 # Allow more concurrency across scenarios
    
    orch = HoneypotOrchestrator()
    results = []

    print("\n" + "="*80)
    print("🚀 Running 10 Test Scenarios from Evaluation Documentation")
    print("="*80 + "\n")

    for i, scenario in enumerate(scenarios, 1):
        print(f"--- Scenario {i}/10: {scenario['description']} ---")
        print(f"📥 Message: {scenario['text']}")
        
        req = HoneypotRequest(
            sessionId=scenario['id'],
            message=Message(sender="scammer", text=scenario['text'], timestamp=int(time.time()*1000)),
            conversationHistory=[],
            metadata=Metadata(channel="SMS", language="English", locale="IN")
        )
        
        # 1. Get Immediate Reply
        res = await orch.process_message(req)
        
        print("📤 Immediate Reply JSON:")
        print(json.dumps(res.model_dump(), indent=2))
        
        results.append(scenario['id'])
        print(f"⏳ Background intel processing started for {scenario['id']}...\n")

    print("\n⏳ Waiting up to 25 seconds for all asynchronous background intelligence and callbacks to complete...\n")
    
    # Wait for all background tasks (3 sec delay + LLM council processing)
    for _ in range(25):
        await asyncio.sleep(1)
        # Check if all sessions have callback_sent
        all_sent = True
        for sid in results:
             session = orch.session_manager.get_session(sid)
             if not session or not session.callback_sent:
                 all_sent = False
                 break
        if all_sent:
             print("\n✅ All callbacks sent successfully early!")
             break
        print(".", end="", flush=True)
        
    await asyncio.sleep(2) # Buffer
        
    print("\n\n" + "="*80)
    print("🕵️ EVALUATION FINAL CALLBACK JSON PAYLOADS:")
    print("="*80 + "\n")

    for scenario in scenarios:
        sid = scenario['id']
        session = orch.session_manager.get_session(sid)
        print(f"\n[{scenario['description'].upper()}] Final Payload:")
        if session and session.final_callback_payload:
            print(json.dumps(session.final_callback_payload, indent=2))
        else:
            print(f"❌ No payload generated for {sid}. Check logs.")
        print("-" * 80)

if __name__ == "__main__":
    # Suppress verbose httpx/orchestrator logs for clean terminal output
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("core.orchestrator").setLevel(logging.WARNING)
    logging.getLogger("core.worker_pool").setLevel(logging.WARNING)
    asyncio.run(run_scenarios())
