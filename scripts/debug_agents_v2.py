
import asyncio
import logging
import json
import httpx
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load env vars
load_dotenv()

from config.settings import get_settings
from engagement.response_generator import ResponseGenerator
from agents.nvidia_agents import NemotronVoter, MultilingualSafetyVoter, MinimaxVoter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_reply_agent():
    print("\n" + "="*50)
    print("🧪 TESTING REPLY AGENT (ResponseGenerator)")
    print("="*50)
    try:
        agent = ResponseGenerator()
        print(f"Model: {agent.model}")
        
        reply, persona, status = await agent.generate(
            message="Your bank account is blocked. Click here to verify.",
            conversation_history=[],
            turn_count=0
        )
        print(f"✅ Status: {status}")
        print(f"✅ Persona: {persona}")
        print(f"✅ Reply: {reply}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

async def test_nemotron():
    print("\n" + "="*50)
    print("🧪 TESTING NEMOTRON VOTER")
    print("="*50)
    try:
        agent = NemotronVoter()
        print(f"Model: {agent.model}")
        
        vote = await agent.vote(
            message="Your bank account is blocked. Click here to verify. Urgent!",
            context="No context",
            session_id="test-session",
            turn_count=0
        )
        print(f"Result:\n{json.dumps(vote.model_dump(), indent=2)}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

async def test_multilingual_safety():
    print("\n" + "="*50)
    print("🧪 TESTING MULTILINGUAL SAFETY VOTER")
    print("="*50)
    try:
        agent = MultilingualSafetyVoter()
        print(f"Model: {agent.model}")
        
        vote = await agent.vote(
            message="Your bank account is blocked. Click here to verify.",
            context="No context",
            session_id="test-session",
            turn_count=0
        )
        print(f"Result:\n{json.dumps(vote.model_dump(), indent=2)}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

async def test_minimax():
    print("\n" + "="*50)
    print("🧪 TESTING MINIMAX VOTER")
    print("="*50)
    try:
        agent = MinimaxVoter()
        print(f"Model: {agent.model}")
        
        vote = await agent.vote(
            message="Your bank account is blocked. Click here to verify.",
            context="No context",
            session_id="test-session",
            turn_count=0
        )
        print(f"Result:\n{json.dumps(vote.model_dump(), indent=2)}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

async def test_judge():
    print("\n" + "="*50)
    print("🧪 TESTING JUDGE AGENT")
    print("="*50)
    try:
        from agents.meta_moderator import JudgeAgent
        from models.schemas import CouncilVote # Import needed for dummy vote
        agent = JudgeAgent()
        print(f"Model: {agent.model}")
        
        # Create dummy votes
        dummy_vote = CouncilVote(
            agent_name="MockAgent",
            is_scam=True,
            confidence=0.9,
            reasoning="Test reasoning",
            scam_type="phishing",
            extracted_intelligence={"suspiciousKeywords": ["urgent"]}
        )
        
        verdict = await agent.adjudication(
            message="Your account is blocked",
            votes=[dummy_vote],
            session_id="test-judge-session",
            turn_count=1
        )
        print(f"✅ Result: {json.dumps(verdict, indent=2)}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

async def main():
    await test_reply_agent()
    await test_nemotron()
    await test_multilingual_safety()
    await test_minimax()
    await test_judge()

if __name__ == "__main__":
    asyncio.run(main())
