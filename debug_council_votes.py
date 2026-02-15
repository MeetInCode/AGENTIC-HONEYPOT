import asyncio
import os
from dotenv import load_dotenv

# Load env helpers
load_dotenv()

# Force specific configuration for debugging if needed, 
# or rely on .env (which we just noticed has the new counts)
# We will trust .env is loaded by settings.

from agents.detection_council import DetectionCouncil
from models.schemas import Message

async def debug_run():
    print("🚀 Initializing Council for Debugging...")
    council = DetectionCouncil()
    
    # TC-339 Data
    history = """
    User: Where is my package?
    Amazon Delivery: Out for delivery today.
    User: Need signature?
    Amazon Delivery: OTP required instead.
    User: Should I share here?
    Amazon Delivery: No, only to agent in person.
    User: Understood.
    """
    
    message = "Your delivery requires OTP confirmation. Share OTP only with delivery agent at doorstep."
    
    print(f"\n📨 Analyzing Message:\n{message}\n")
    
    votes, verdict = await council.analyze(
        message=message,
        context=history,
        session_id="debug-session-339"
    )
    
    print("\n🧐 VOTE BREAKDOWN:")
    for vote in votes:
        icon = "❌ SCAM" if vote.is_scam else "✅ SAFE"
        print(f"{icon} {vote.agent_name}: {vote.confidence} - {vote.reasoning}")
        
    print(f"\n⚖️ VERDICT: Is Scam? {verdict.is_scam} (Confidence: {verdict.confidence})")

if __name__ == "__main__":
    asyncio.run(debug_run())
