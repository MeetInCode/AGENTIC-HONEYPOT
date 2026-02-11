"""
Manual end‑to‑end pipeline test for the Agentic Honeypot.

This script:
  - Instantiates the HoneypotOrchestrator directly (no HTTP layer)
  - Sends multiple messages across several sessions (bank fraud, UPI scam, benign)
  - Lets the 5‑agent LLM council + Judge + callback pipeline run
  - Uses `rich` to print a compact summary of each API response in the terminal

NOTE:
  - All the detailed, stage‑by‑stage Rich prints (incoming message, council votes,
    agent response, callback payload) are already handled inside the orchestrator
    via `utils.rich_printer`. This test file only adds a high‑level table.
  - Make sure your environment variables/API keys are configured before running.

Usage (from project root):
    python -m test_honeypot_pipeline
"""

import asyncio
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich import box

from core.orchestrator import HoneypotOrchestrator
from models.schemas import HoneypotRequest, Message, Metadata


console = Console()


def _build_request(
    session_id: str,
    sender: str,
    text: str,
    history: list,
    channel: str = "SMS",
    language: str = "English",
    locale: str = "IN",
) -> HoneypotRequest:
    """Helper to build a HoneypotRequest with realistic metadata."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    msg = Message(sender=sender, text=text, timestamp=timestamp)
    meta = Metadata(channel=channel, language=language, locale=locale)
    return HoneypotRequest(
        sessionId=session_id,
        message=msg,
        conversationHistory=history,
        metadata=meta,
    )


async def run_scenarios():
    """Run a few hard‑coded conversations through the full pipeline."""
    orchestrator = HoneypotOrchestrator()

    # Simple in‑memory history tracker for building conversationHistory
    histories: dict[str, list[dict]] = {}

    # Define test scenarios
    scenarios = [
        {
            "name": "Bank OTP freeze scam",
            "session_id": "session-bank-001",
            "messages": [
                "Your SBI account will be blocked today due to suspicious activity. Share OTP immediately to keep it active.",
                "You are not taking this seriously. Last reminder: send the 6 digit OTP now or account will be frozen.",
            ],
        },
        {
            "name": "UPI refund / lottery scam",
            "session_id": "session-upi-002",
            "messages": [
                "Congratulations! You have won Rs 50,000 PhonePe cashback. To receive amount send Rs 499 processing fee to claim.prize@ybl.",
                "Offer expires in 30 minutes. Send fee now or prize will be cancelled. Click http://phonepe-cashback-offer.xyz to verify.",
            ],
        },
        {
            "name": "Benign support query (control)",
            "session_id": "session-benign-003",
            "messages": [
                "Hi, I want to know my account balance, can you send me a mini statement?",
            ],
        },
    ]

    # Pretty header
    console.print()
    console.rule("[bold cyan]🧪 Agentic Honeypot — End‑to‑End Pipeline Test[/bold cyan]", style="cyan")
    console.print()

    results_table = Table(title="Synchronous API Replies", show_lines=True, box=box.ROUNDED)
    results_table.add_column("Scenario", style="cyan", min_width=22)
    results_table.add_column("Session", style="magenta", min_width=18)
    results_table.add_column("Turn", justify="right")
    results_table.add_column("Scam?", justify="center")
    results_table.add_column("Conf.", justify="center")
    results_table.add_column("Reply (truncated)", style="white", max_width=60, overflow="fold")

    for scenario in scenarios:
        session_id = scenario["session_id"]
        histories.setdefault(session_id, [])

        console.print()
        console.print(
            Panel(
                Text(f"{scenario['name']}  (sessionId={session_id})", style="bold"),
                border_style="cyan",
            )
        )

        for idx, text in enumerate(scenario["messages"], start=1):
            history = histories[session_id]
            request = _build_request(
                session_id=session_id,
                sender="scammer",
                text=text,
                history=history,
            )

            # --- Show input request JSON ---
            console.print()
            console.print(Panel(
                Syntax(request.model_dump_json(indent=2), "json", theme="monokai", line_numbers=False),
                title=f"📥 Input HoneypotRequest (turn {idx})",
                border_style="blue",
            ))

            # Call orchestrator — this triggers reply path + async intel path.
            response = await orchestrator.process_message(request)

            # --- Show synchronous reply JSON ---
            console.print(Panel(
                Syntax(response.model_dump_json(indent=2), "json", theme="monokai", line_numbers=False),
                title=f"💬 HoneypotResponse (turn {idx})",
                border_style="green",
            ))

            # Maintain our simple history mirror (for next request)
            history.append(
                {
                    "sender": "scammer",
                    "text": text,
                    "timestamp": request.message.timestamp,
                }
            )
            if response.reply:
                history.append(
                    {
                        "sender": "user",
                        "text": response.reply,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                )

            # Record summary row
            scam_icon = "🔴" if response.scamDetected else "🟢"
            conf_str = f"{response.confidence:.0%}"
            reply_preview = (response.reply or "")[:160]
            results_table.add_row(
                scenario["name"],
                session_id,
                str(idx),
                scam_icon,
                conf_str,
                reply_preview,
            )

        # After finishing a scenario's messages, sleep > inactivity_timeout_seconds
        # so the Judge + callback pipeline has a chance to fire.
        console.print(
            Text(
                "Waiting 6 seconds to allow inactivity timer → Judge LLM → callback...",
                style="dim",
            )
        )
        await asyncio.sleep(6)

        # --- After inactivity: inspect council votes and final callback for this session ---
        session = orchestrator.session_manager.get_session(session_id)
        if session:
            # All council votes (across all turns) stored on the session
            if session.council_votes:
                votes_json = [
                    {
                        "agent": v.agent_name,
                        "isScam": v.is_scam,
                        "confidence": round(v.confidence, 3),
                        "scamType": v.scam_type,
                        "extractedIntelligence": v.extracted_intelligence,
                        "agentNotes": v.reasoning,
                    }
                    for v in session.council_votes
                ]
                console.print(Panel(
                    Syntax(
                        HoneypotOrchestrator.__annotations__  # dummy to satisfy linter, replaced below
                        if False else  # never executed
                        "",
                        "text",
                    ),
                    title="",
                ))
                console.print(Panel(
                    Syntax(
                        __import__("json").dumps({"votes": votes_json}, indent=2, ensure_ascii=False),
                        "json",
                        theme="monokai",
                        line_numbers=False,
                    ),
                    title="🗳️ All 5 Council Members — Aggregated Votes (per turn)",
                    border_style="magenta",
                ))

            # Final callback payload prepared by Judge + callback service
            if session.final_callback_payload:
                console.print(Panel(
                    Syntax(
                        __import__("json").dumps(session.final_callback_payload, indent=2, ensure_ascii=False),
                        "json",
                        theme="monokai",
                        line_numbers=False,
                    ),
                    title="🚀 Final Callback Payload (Judge‑aggregated)",
                    border_style="yellow",
                ))

    console.print()
    console.print(results_table)
    console.print()
    console.rule("[bold green]✅ Pipeline test run complete[/bold green]", style="green")
    console.print()


if __name__ == "__main__":
    asyncio.run(run_scenarios())

