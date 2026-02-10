"""
Test Script: Models & Participation Verification
Tests:
1. Response Generation (llama-3.3-70b-versatile)
2. Full Detection Council (participation check)
   - Nemotron (nvidia/nemotron-4-340b-instruct)
   - DeepSeek (deepseek-ai/deepseek-r1-distill-llama-8b)
   - Minimax (minimaxai/minimax-m2.1)
   - LlamaScout
   - GptOss
3. Callback Payload formatting
"""

import sys
import os

# Add parent dir to path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import json
import logging
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Setup environment
from dotenv import load_dotenv
load_dotenv()

# Import core components
from engagement.response_generator import ResponseGenerator
from agents.detection_council import DetectionCouncil
from services.intelligence_extractor import IntelligenceExtractor
from models.schemas import CouncilVote
from utils.rich_printer import print_council_votes, print_agent_response, print_callback_payload

# Configure logging to suppress debug noise
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_script")
# Force UTF-8 file output, no color for reliable reading
console = Console(file=open("test_results.txt", "w", encoding="utf-8"), force_terminal=False, no_color=True)

async def run_tests():
    console.rule("[bold red]🧪 STARTING HONEYPOT MODEL TESTS[/bold red]")
    
    # ─── Test Data ───
    dummy_message = "Congratulations! You won Rs 50000 in Jio Lucky Draw! Send Rs 500 to claim@ybl to claim your prize. Call +91-8765432100."
    history = []  # No history for first turn
    context = "No prior conversation."

    console.print(Panel(dummy_message, title="Start Dummy Input", style="white on blue"))

    # ─── Test 1: Response Generation (llama-3.3-70b-versatile) ───
    console.rule("[bold cyan]Test 1: Engagement Response (llama-3.3-70b)[/bold cyan]")
    
    response_gen = ResponseGenerator()
    start = asyncio.get_event_loop().time()
    
    # Generate response
    reply, persona_id = await response_gen.generate(
        message=dummy_message,
        conversation_history=history,
        scam_type="lottery_scam",
        persona_id="ramesh_kumar",
        turn_count=1
    )
    elapsed = asyncio.get_event_loop().time() - start
    
    print_agent_response(reply, "Ramesh Kumar", elapsed)
    
    # Check if response is good (simple heuristic)
    if len(reply) > 200:
        console.print("[bold yellow]⚠️  Warning: Response might be too long![/bold yellow]")
    else:
        console.print("[bold green]✅ Response length looks good.[/bold green]")


    # ─── Test 2: Detection Council (All Models) ───
    console.rule("[bold magenta]Test 2: Full Detection Council Participation[/bold magenta]")
    
    council = DetectionCouncil()
    
    # We want to see INDIVIDUAL votes, so we'll access the voters directly
    # logic from DetectionCouncil.analyze, but instrumented
    
    voters = council.voters
    console.print(f"Loaded {len(voters)} voters: {[v.__class__.__name__ for v in voters]}")
    
    start_council = asyncio.get_event_loop().time()
    
    # Run all voters with dummy session data
    vote_tasks = [voter.vote(dummy_message, context, "test-session-123", 1) for voter in voters]
    results = await asyncio.gather(*vote_tasks, return_exceptions=True)
    
    # Process results
    valid_votes = []
    for i, res in enumerate(results):
        voter_name = voters[i].__class__.__name__
        if isinstance(res, Exception):
            console.print(f"[bold red]❌ {voter_name} FAILED:[/bold red] {res}")
            # Add dummy failed vote for table
            valid_votes.append(CouncilVote(
                agent_name=voter_name, 
                is_scam=False, 
                confidence=0.0, 
                reasoning=f"ERROR: {str(res)[:50]}",
                extracted_intelligence={}
            ))
        else:
            console.print(f"[bold green]✅ {voter_name} replied[/bold green] (Conf: {res.confidence:.2f})")
            valid_votes.append(res)
            
    elapsed_council = asyncio.get_event_loop().time() - start_council
    print_council_votes(valid_votes, elapsed_council)
    
    # ─── Test 3: Judge Verdict ───
    # We can assume Judge works if voters work, but let's test just in case
    # This just aggregates the valid votes
    
    # ─── Test 4: Callback JSON ───
    console.rule("[bold yellow]Test 3: Callback JSON Payload[/bold yellow]")
    
    # Extract intel (using extractor)
    extractor = IntelligenceExtractor()
    intel = await extractor.extract([{"sender": "scammer", "text": dummy_message}])
    
    filtered_intel = {
        k: v for k, v in intel.items() 
        if k in {"bankAccounts", "upiIds", "phishingLinks", "phoneNumbers", "suspiciousKeywords"}
    }
    
    payload = {
        "sessionId": "test-script-001",
        "scamDetected": True,
        "totalMessagesExchanged": 2,
        "extractedIntelligence": filtered_intel,
        "agentNotes": "Detected scam based on urgency and claim@ybl UPI ID."
    }
    
    print_callback_payload(payload, 0.1, 200)

    console.rule("[bold blue]Test 4: Judge Aggregation[/bold blue]")
    from agents.meta_moderator import JudgeAgent
    from models.schemas import CouncilVote
    
    judge = JudgeAgent()
    votes = [
        CouncilVote(agent_name="Nemotron", is_scam=True, confidence=0.9, reasoning="Scam detected", extracted_intelligence={"upiIds": ["scam@ybl"]}),
        CouncilVote(agent_name="DeepSeek", is_scam=True, confidence=0.9, reasoning="Scam detected", extracted_intelligence={"phoneNumbers": ["+919999999999"]}),
        CouncilVote(agent_name="Minimax", is_scam=True, confidence=0.9, reasoning="Scam detected", extracted_intelligence={}),
        CouncilVote(agent_name="LlamaScout", is_scam=True, confidence=0.9, reasoning="Scam", extracted_intelligence={}),
        CouncilVote(agent_name="GptOss", is_scam=True, confidence=0.9, reasoning="Scam", extracted_intelligence={})
    ]
    
    try:
        final_json = await judge.adjudication(dummy_message, votes, "test-judge-123", 5)
        if "sessionId" in final_json and "extractedIntelligence" in final_json:
             console.print(f"[bold green]✅ Judge Output Valid:[/bold green] {json.dumps(final_json)[:100]}...")
        else:
             console.print(f"[bold red]❌ Judge Output Invalid:[/bold red] {final_json}")
    except Exception as e:
        console.print(f"[bold red]❌ Judge Failed:[/bold red] {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())
