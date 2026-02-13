"""
Debug script for Council Agents (Groq & NVIDIA).
Test individual voters to ensure they are responding correctly.
"""
import sys
import os
import asyncio
import logging
import traceback

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.nvidia_agents import MinimaxVoter, NemotronVoter
from agents.groq_agents import LlamaScoutVoter, GptOssVoter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_voter(voter_class, name):
    print(f"\n{'='*20} TESTING {name} {'='*20}")
    message = "Congratulations! You won Rs 50000 in Jio Lucky Draw! Send Rs 500 to claim@ybl via UPI immediately to claim your prize before it expires today."
    context = "No prior context."
    
    try:
        print(f"Initializing {name}...")
        voter = voter_class()
        
        print(f"Sending vote request to {name}...")
        start_time = asyncio.get_event_loop().time()
        result = await voter.vote(message, context, "debug-session-001", 1)
        end_time = asyncio.get_event_loop().time()
        
        print(f"✅ {name} SUCCESS ({end_time - start_time:.2f}s)")
        print(f"Is Scam: {result.is_scam}")
        print(f"Confidence: {result.confidence}")
        print(f"Reasoning: {result.reasoning}")
        print(f"Extracted: {result.extracted_intelligence}")
        
    except Exception as e:
        print(f"❌ {name} FAILED")
        print(f"Error: {str(e)}")
        traceback.print_exc()

async def debug_all_agents():
    print("🚀 Starting Council Agents Debug...")
    
    # Test Groq Agents
    await test_voter(LlamaScoutVoter, "LlamaScoutVoter (Groq)")
    await test_voter(GptOssVoter, "GptOssVoter (Groq)")
    
    # Test NVIDIA Agents
    await test_voter(NemotronVoter, "NemotronVoter (NVIDIA)")
    await test_voter(MinimaxVoter, "MinimaxVoter (NVIDIA)")
    
    print("\n🏁 Debug Complete")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_all_agents())
