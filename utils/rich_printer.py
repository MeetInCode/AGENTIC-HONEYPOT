"""
Rich Console Printer — beautiful server-side pipeline logging.

Prints at each stage of the honeypot pipeline:
  1. 📨 Incoming message received  (with full request JSON)
  2. 🗳️ LLM Council votes          (table per voter)
  3. ⚖️ Judge verdict               (panel with reasoning)
  4. 💬 Agent response sent         (with API response JSON)
  5. 📤 Callback payload dispatched (with full callback JSON)

Each stage shows response time. Uses `rich` for panels, tables, syntax, and colors.
"""

import json
from typing import Optional

def print_incoming_message(
    session_id: str,
    sender: str,
    text: str,
    turn: int,
    channel: str = "SMS",
    raw_request: dict = None,
):
    """Print the received scammer message with full request JSON."""
    if raw_request:
        print("\n=== INCOMING MESSAGE ===")
        print(json.dumps(raw_request, indent=2))

def print_council_votes(votes: list, elapsed_seconds: float):
    pass

def print_judge_verdict(verdict, judge_elapsed: float):
    pass

def print_agent_response(response_text: str, persona_name: str, elapsed_seconds: float):
    pass

def print_api_response(response_dict: dict, total_elapsed: float):
    """Print the full API response JSON that was returned to the caller."""
    print("\n=== REPLY AGENT JSON ===")
    print(json.dumps(response_dict, indent=2))

def print_callback_payload(payload: dict, elapsed: float, status: int = 200):
    print("\n=== CALLBACK JSON ===")
    print(json.dumps(payload, indent=2))

def print_pipeline_summary(total_elapsed: float, session_id: str, scam: bool, note: Optional[str] = None):
    pass
