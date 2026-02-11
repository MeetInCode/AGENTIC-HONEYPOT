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
import time
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich import box

console = Console()


def _json_panel(data: dict, title: str, border_style: str = "dim") -> Panel:
    """Create a panel with syntax-highlighted JSON."""
    json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False, word_wrap=True)
    return Panel(syntax, title=title, border_style=border_style, box=box.ROUNDED, padding=(0, 1))


def print_incoming_message(
    session_id: str,
    sender: str,
    text: str,
    turn: int,
    channel: str = "SMS",
    raw_request: dict = None,
):
    """Print the received scammer message with full request JSON."""
    console.print()
    console.rule("[bold blue]📨  INCOMING MESSAGE[/bold blue]", style="blue")
    console.print()

    # Summary line
    info = Table(show_header=False, box=None, padding=(0, 2))
    info.add_column("key", style="dim", min_width=10)
    info.add_column("val")
    info.add_row("Session", Text(session_id, style="cyan"))
    info.add_row("Turn", Text(str(turn), style="yellow"))
    info.add_row("Channel", Text(channel, style="dim"))
    info.add_row("Sender", Text(sender, style="red bold"))
    console.print(info)

    # Message text
    console.print()
    console.print(Panel(
        Text(text, style="white bold"),
        title="Message Text",
        border_style="blue",
        box=box.SIMPLE,
    ))

    # Full request JSON
    if raw_request:
        console.print(_json_panel(raw_request, "📥 Raw Request JSON", "blue"))


def print_council_votes(votes: list, elapsed_seconds: float):
    """Print each voter's result in a table."""
    console.print()
    console.rule("[bold magenta]🗳️  LLM COUNCIL VOTES[/bold magenta]", style="magenta")
    console.print()

    table = Table(
        box=box.ROUNDED,
        border_style="magenta",
        show_lines=True,
        pad_edge=True,
    )

    table.add_column("Agent", style="cyan bold", min_width=18)
    table.add_column("Scam?", justify="center", min_width=8)
    table.add_column("Conf", justify="center", min_width=7)
    table.add_column("Type", style="yellow", min_width=14)
    table.add_column("Reasoning", max_width=55, overflow="fold")

    for vote in votes:
        scam_icon = "🔴 YES" if vote.is_scam else "🟢 NO"
        conf = f"{vote.confidence:.0%}"

        if vote.confidence >= 0.8:
            conf_style = "red bold"
        elif vote.confidence >= 0.5:
            conf_style = "yellow"
        else:
            conf_style = "green"

        reasoning_short = vote.reasoning[:120] + "…" if len(vote.reasoning) > 120 else vote.reasoning

        table.add_row(
            vote.agent_name,
            scam_icon,
            Text(conf, style=conf_style),
            vote.scam_type,
            reasoning_short,
        )

    console.print(table)

    # Raw votes as JSON
    votes_json = [
        {
            "agent": v.agent_name,
            "isScam": v.is_scam,
            "confidence": round(v.confidence, 3),
            "scamType": v.scam_type,
            "reasoning": v.reasoning[:200],
            "extractedIntelligence": v.extracted_intelligence,
        }
        for v in votes
    ]
    console.print(_json_panel({"votes": votes_json}, "🗳️ Council Votes JSON", "magenta"))

    console.print(
        Text(f"  ⏱  Council voting completed in {elapsed_seconds:.2f}s", style="dim magenta")
    )


def print_judge_verdict(verdict, judge_elapsed: float):
    """Print the judge's final verdict."""
    console.print()
    console.rule("[bold]⚖️  JUDGE VERDICT[/bold]", style="red" if verdict.is_scam else "green")
    console.print()

    is_scam = verdict.is_scam
    conf = verdict.confidence

    if is_scam:
        border = "red"
        icon = "🚨"
        verdict_text = "SCAM DETECTED"
        style = "bold white on red"
    else:
        border = "green"
        icon = "✅"
        verdict_text = "SAFE — No scam"
        style = "bold white on green"

    content = Text()
    content.append(f"Decision:   ", style="dim")
    content.append(f"{icon} {verdict_text}\n", style=style)
    content.append(f"Confidence: ", style="dim")
    content.append(f"{conf:.0%}\n", style="bold")
    content.append(f"Scam Type:  ", style="dim")
    content.append(f"{verdict.scam_type}\n", style="yellow bold")
    content.append(f"Vote Tally: ", style="dim")
    content.append(f"{verdict.scam_votes}/{verdict.voter_count} voted scam\n\n", style="bold")
    content.append(f"Reasoning:\n", style="dim")
    content.append(verdict.reasoning[:300] if verdict.reasoning else "N/A", style="italic")

    console.print(Panel(content, border_style=border, box=box.HEAVY))

    # Judge verdict as JSON
    verdict_json = {
        "isScam": verdict.is_scam,
        "confidence": round(verdict.confidence, 3),
        "scamType": verdict.scam_type,
        "scamVotes": verdict.scam_votes,
        "voterCount": verdict.voter_count,
        "reasoning": verdict.reasoning,
    }
    console.print(_json_panel(verdict_json, "⚖️ Judge Verdict JSON", border))

    console.print(
        Text(f"  ⏱  Judge deliberation took {judge_elapsed:.2f}s", style=f"dim {border}")
    )


def print_agent_response(response_text: str, persona_name: str, elapsed_seconds: float):
    """Print the agent's generated response."""
    console.print()
    console.rule("[bold green]💬  AGENT RESPONSE[/bold green]", style="green")
    console.print()

    content = Text()
    content.append("Persona: ", style="dim")
    content.append(f"{persona_name}\n\n", style="green bold")
    content.append(response_text, style="white bold")

    console.print(Panel(content, border_style="green", box=box.DOUBLE))
    console.print(
        Text(f"  ⏱  Response generated in {elapsed_seconds:.2f}s", style="dim green")
    )


def print_api_response(response_dict: dict, total_elapsed: float):
    """Print the full API response JSON that was returned to the caller."""
    console.print()
    console.rule("[bold cyan]📤  API RESPONSE SENT[/bold cyan]", style="cyan")
    console.print()

    console.print(_json_panel(response_dict, "Response JSON", "cyan"))
    console.print(
        Text(f"  ⏱  Total reply latency: {total_elapsed:.2f}s", style="dim cyan")
    )



def print_callback_payload(payload: dict, elapsed: float, status: int = 200):
    console.print()
    if status in (200, 201, 202):
        console.rule(f"[bold green]🚀  CALLBACK DISPATCHED (HTTP {status})[/bold green]", style="green")
    else:
        console.rule(f"[bold red]❌  CALLBACK FAILED (HTTP {status})[/bold red]", style="red")
    
    # Engagement stats
    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column(style="cyan bold")
    stats_table.add_column(style="white")
    
    stats_table.add_row("Session ID:", payload.get("sessionId", "N/A"))
    # totalMessagesExchanged is now top level
    total_msgs = payload.get("totalMessagesExchanged", 0)
    stats_table.add_row("Msgs Exchanged:", str(total_msgs))
    
    # Extracted Intel Table
    intel = payload.get("extractedIntelligence", {})
    intel_table = Table(title="Extracted Intelligence", box=box.ROUNDED, show_header=True, header_style="bold yellow")
    intel_table.add_column("Type", style="cyan")
    intel_table.add_column("Value", style="white")
    
    if intel:
        # Convert Pydantic model to dict if needed (it comes as dict from service usually)
        if hasattr(intel, "dict"):
            intel = intel.dict()
            
        for key, values in intel.items():
            if values:
                if isinstance(values, list):
                    for v in values:
                         intel_table.add_row(key, str(v))
                else:
                    intel_table.add_row(key, str(values))
    
    # Agent Notes
    notes = payload.get("agentNotes", "N/A")
    
    # Layout
    console.print()
    console.print(stats_table)
    console.print()
    console.print(intel_table)
    console.print(Panel(notes, title="Agent Notes", border_style="magenta"))
    
    # Full JSON at bottom
    console.print()
    console.print(_json_panel(payload, "Full Callback Payload", "green" if status < 400 else "red")) 
    
    console.print(
        Text(f"  ⏱  Callback completed in {elapsed:.2f}s", style="dim green")
    )


def print_pipeline_summary(total_elapsed: float, session_id: str, scam: bool, note: Optional[str] = None):
    """Print a final one-line summary of the reply path."""
    icon = "🔴" if scam else "🟢"
    style = "red" if scam else "green"
    
    text = f"{icon}  Reply sent for {session_id} in {total_elapsed:.2f}s"
    if note:
        text += f" | {note}"

    console.print()
    console.rule(
        f"[bold {style}]{text}[/bold {style}]",
        style=style,
    )
    console.print()
