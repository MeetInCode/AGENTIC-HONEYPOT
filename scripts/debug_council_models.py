"""
Debug script for NVIDIA agents and Response Generator.
Prints RAW API responses to debug low confidence scores.
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import logging
from agents.nvidia_agents import NemotronVoter, DeepSeekVoter, MinimaxVoter
from engagement.response_generator import ResponseGenerator

# Configure logging to show everything
logging.basicConfig(level=logging.INFO)

async def debug_agents():
    message = "Congratulations! You won Rs 50000 in Jio Lucky Draw! Send Rs 500 to claim@ybl to claim your prize."
    context = "No prior context."

    print("\n" + "="*50)
    print("🤖 DEBUG: RESPONSE GENERATOR (llama-3.3-70b)")
    print("="*50)
    try:
        gen = ResponseGenerator()
        reply, pid = await gen.generate(message, [], "lottery_scam", "ramesh_kumar", 1)
        print(f"\n[Response Text]:\n{reply}")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\n" + "="*50)
    print("🤖 DEBUG: NEMOTRON VOTER")
    print("="*50)
    try:
        voter = NemotronVoter()
        # We need to hook into the _call_nvidia method or just run vote and see logging
        # But logging is to stderr/stdout depending on config. 
        # I'll rely on the logger in nvidia_agents.py if it logs raw response.
        # If not, I'll print the result details.
        result = await voter.vote(message, context, "debug-session", 1)
        print(f"\n[Parsed Result]:\nScam: {result.is_scam}\nConf: {result.confidence}\nReason: {result.reasoning}")
        print(f"Extracted: {result.extracted_intelligence}")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\n" + "="*50)
    print("🤖 DEBUG: DEEPSEEK VOTER")
    print("="*50)
    try:
        voter = DeepSeekVoter()
        result = await voter.vote(message, context, "debug-session", 1)
        print(f"\n[Parsed Result]:\nScam: {result.is_scam}\nConf: {result.confidence}\nReason: {result.reasoning}")
        print(f"Extracted: {result.extracted_intelligence}")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\n" + "="*50)
    print("🤖 DEBUG: MINIMAX VOTER")
    print("="*50)
    try:
        voter = MinimaxVoter()
        result = await voter.vote(message, context, "debug-session", 1)
        print(f"\n[Parsed Result]:\nScam: {result.is_scam}\nConf: {result.confidence}\nReason: {result.reasoning}")
        print(f"Extracted: {result.extracted_intelligence}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(debug_agents())
