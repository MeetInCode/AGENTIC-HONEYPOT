"""
Test Script: Heavy Load / Stress Test
Scenario: Long conversation (30+ messages) with "Pig Butchering" / Investment Scam context.
Tests capability of agents to handle large context windows and subtle scam cues.
"""

import sys
import os
import asyncio
import json
import logging
from rich.console import Console
from rich.panel import Panel

# Setup environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
load_dotenv()

from agents.detection_council import DetectionCouncil
from agents.meta_moderator import JudgeAgent
from models.schemas import CouncilVote
from utils.rich_printer import print_council_votes, print_judge_verdict

# Configure logging
logging.basicConfig(level=logging.INFO)
console = Console(file=open("heavy_test_results.txt", "w", encoding="utf-8"), force_terminal=False, no_color=True)

# ─── MOCKED CONVERSATION HISTORY (30 Messages) ───
HISTORY = [
    {"sender": "scammer", "text": "Hi, is this Sarah? I found this number in my contacts."},
    {"sender": "agent", "text": "No, this is not Sarah. You have the wrong number."},
    {"sender": "scammer", "text": "Oh strictly sorry! I must have mistyped. You are very kind to reply though."},
    {"sender": "agent", "text": "That's okay. Have a nice day."},
    {"sender": "scammer", "text": "You too! By the way, I am Li Wei. I am from Hong Kong but living in London now. Where are you from?"},
    {"sender": "agent", "text": "I am from Delhi."},
    {"sender": "scammer", "text": "India is beautiful! I visited Mumbai last year for business. I work in import/export and financial analysis."},
    {"sender": "agent", "text": "That sounds interesting. I am a software engineer."},
    {"sender": "scammer", "text": "Wow, smart! Do you invest in crypto? The market is very good right now."},
    {"sender": "agent", "text": "I have heard of it but never inspected it closely."},
    {"sender": "scammer", "text": "You should! My uncle is a senior analyst at Goldman Sachs, he gives me inside signals. We made 30% last week."},
    {"sender": "agent", "text": "30% is a lot. Is it safe?"},
    {"sender": "scammer", "text": "Yes, completely safe if you use the right platform. We use specific short-term nodes. I can teach you."},
    {"sender": "agent", "text": "I don't have much money to risk."},
    {"sender": "scammer", "text": "You can start small. Just $100 to see how it works. I will guide you step by step. We are friends now, I want to help you."},
    {"sender": "agent", "text": "Okay, maybe later."},
    {"sender": "scammer", "text": "Don't wait too long. The market moves fast. Today there is a special node opening."},
    {"sender": "agent", "text": "What do I need to do?"},
    {"sender": "scammer", "text": "First download Trust Wallet. I will give you the link to our defi node platform."},
    {"sender": "agent", "text": "I downloaded it."},
    {"sender": "scammer", "text": "Good. Now go to the browser inside the wallet and type 'defi-secure-node-vip.com'"},
    {"sender": "agent", "text": "It asks to connect wallet."},
    {"sender": "scammer", "text": "Yes, click connect. It is a smart contract interaction to authorize the mining pool."},
    {"sender": "agent", "text": "Done."},
    {"sender": "scammer", "text": "Great! Now you can see your earnings grow every 6 hours. But to activate the VIP tier you need minimum $1000 USDT."},
    {"sender": "agent", "text": "I thought you said $100?"},
    {"sender": "scammer", "text": "Yes, for basic. But VIP is much better returns. I really recommend you try to find $1000."},
    {"sender": "agent", "text": "I can only do $500."},
    {"sender": "scammer", "text": "Okay, I can help you with the rest maybe. But you need to deposit the $500 now immediately so we don't lose the slot."},
    {"sender": "agent", "text": "I am trying but my bank is blocking it."}
]

# The "Tough" Request Message
LAST_MESSAGE = "Call your bank and tell them it is for a family member! Use the P2P merchant I sent you. Send the screenshot as soon as possible. Trust me, we will make huge profit tonight. Don't let me down."

async def run_heavy_load_test():
    console.rule("[bold red]🧪 STARTING HEAVY LOAD TEST (30+ Messages)[/bold red]")
    
    # Context Formulation
    context_str = "\n".join([f"{msg['sender'].upper()}: {msg['text']}" for msg in HISTORY])
    console.print(f"Context Length: {len(context_str)} chars")
    
    # ─── 1. Run Detection Council ───
    console.rule("[bold magenta]Step 1: Council Voting[/bold magenta]")
    council = DetectionCouncil()
    voters = council.voters
    
    start_council = asyncio.get_event_loop().time()
    
    # Execute votes
    vote_tasks = [v.vote(LAST_MESSAGE, context_str, "heavy-test-session", 31) for v in voters]
    results = await asyncio.gather(*vote_tasks, return_exceptions=True)
    
    # Reconcile Results
    valid_votes = []
    for i, res in enumerate(results):
        name = voters[i].__class__.__name__
        if isinstance(res, Exception):
            console.print(f"[bold red]❌ {name} FAILED:[/bold red] {repr(res)}")
            # Mock fail vote
            valid_votes.append(CouncilVote(
                agent_name=name,
                is_scam=False,
                confidence=0.0,
                reasoning=f"ERROR: {repr(res)}",
                extracted_intelligence={}
            ))
        else:
            if res.confidence == 0.0:
                 console.print(f"[bold red]⚠️ {name} Returned 0.0 Confidence:[/bold red] {res.reasoning}")
            else:
                 console.print(f"[bold green]✅ {name} replied[/bold green] (Conf: {res.confidence:.2f})")
            valid_votes.append(res)
            
    council_elapsed = asyncio.get_event_loop().time() - start_council
    print_council_votes(valid_votes, council_elapsed)
    
    # ─── 2. Run Judge ───
    console.rule("[bold blue]Step 2: Judge Adjudication[/bold blue]")
    judge = JudgeAgent()
    
    start_judge = asyncio.get_event_loop().time()
    final_payload = await judge.adjudication(LAST_MESSAGE, valid_votes, "heavy-test-session", 31)
    judge_elapsed = asyncio.get_event_loop().time() - start_judge
    
    # Show strict JSON output
    console.print(Panel(json.dumps(final_payload, indent=2), title="Judge Final Payload", style="white on blue"))
    
    if "conversationLog" not in final_payload:
         console.print("[bold green]✅ Strict Format Check Passed: No conversationLog[/bold green]")
    else:
         console.print("[bold red]❌ Strict Format Check Failed: conversationLog present[/bold red]")

    # ─── 3. Print Final Callback ───
    from utils.rich_printer import print_callback_payload
    # CallbackService logic simulation (strictly filtering)
    callback_payload = final_payload.copy()
    if "extractedIntelligence" in callback_payload:
        raw_intel = callback_payload["extractedIntelligence"]
        filtered_intel = {
            k: v for k, v in raw_intel.items() 
            if k in {"bankAccounts", "upiIds", "phishingLinks", "phoneNumbers", "suspiciousKeywords"}
        }
        callback_payload["extractedIntelligence"] = filtered_intel
    
    # Print to stdout (user visible)
    try:
        print_callback_payload(callback_payload, judge_elapsed, 200)
    except Exception:
        pass

    # Print to file console (artifact)
    console.rule("[bold green]FINAL CALLBACK PAYLOAD[/bold green]")
    console.print(json.dumps(callback_payload, indent=2))
    
    # Debugging DeepSeek empty error
    # (Already handled by previous steps if I change the loop)

    if "conversationLog" not in final_payload:
         console.print("[bold green]✅ Strict Format Check Passed: No conversationLog[/bold green]")
    else:
         console.print("[bold red]❌ Strict Format Check Failed: conversationLog present[/bold red]")

if __name__ == "__main__":
    asyncio.run(run_heavy_load_test())
