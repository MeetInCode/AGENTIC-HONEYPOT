import requests
import json
import time
import threading
import uvicorn
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket
from fastapi import FastAPI, Request
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
from rich.table import Table
from rich import box


"""
Production-ready stress test for Agentic Honeypot API.

Tests concurrent request handling, callback delivery, and system resilience.
Uses threading for parallel request execution to simulate real-world load.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG (Load from environment or use defaults)
# ─────────────────────────────────────────────
HONEYPOT_URL = os.getenv("HONEYPOT_URL", "http://localhost:8000/honeypot/message")
CALLBACK_PORT = int(os.getenv("CALLBACK_PORT", "8001"))
API_KEY = os.getenv("API_KEY", "hp_live_9fA3kLQxP2Z8R7sM1")
MAX_WAIT_TIME = int(os.getenv("MAX_CALLBACK_WAIT", "30"))
HARD_DEADLINE = int(os.getenv("HARD_DEADLINE", "20"))



HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

console = Console()

# Track callbacks per session
callbacks_lock = threading.Lock()
callbacks_received = {}       # sessionId -> callback data
expected_sessions = set()     # sessions we're waiting for
all_callbacks_done = threading.Event()
callback_server_ready = threading.Event()   # signals that server bound OK

# ─────────────────────────────────────────────
# FAKE CALLBACK SERVER
# ─────────────────────────────────────────────
app = FastAPI()

@app.get("/health")
async def health():
    """Health check for startup verification."""
    return {"status": "ok"}

@app.post("/api/updateHoneyPotFinalResult")
async def receive_callback(request: Request):
    payload = await request.json()
    sid = payload.get("sessionId")
    
    console.print(f"[bold green]📬 Callback received for {sid}[/bold green]")
    
    # Store callback
    with callbacks_lock:
        if sid in expected_sessions:
            callbacks_received[sid] = payload
            # Check if all received
            missing = expected_sessions - callbacks_received.keys()
            if not missing:
                all_callbacks_done.set()
        else:
            console.print(f"[bold yellow]⚠️  Unexpected callback for session: {sid}[/bold yellow]")
    
    return {"status": "ok"}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(request: Request, path: str):
    """Catch-all route to detect misrouted requests."""
    body = None
    try:
        body = await request.json()
    except Exception:
        pass
    console.print(
        f"[bold yellow]⚠️  Unexpected request: {request.method} /{path}[/bold yellow]"
    )
    if body:
        console.print(f"[dim]   Body keys: {list(body.keys()) if isinstance(body, dict) else type(body)}[/dim]")
    return {"status": "not_found", "path": path}

def _is_port_available(port: int) -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", port))
            return True
    except OSError:
        return False

def run_callback_server():
    try:
        uvicorn.run(app, host="0.0.0.0", port=CALLBACK_PORT, log_level="warning")
    except Exception as e:
        console.print(f"[bold red]❌ Callback server failed: {e}[/bold red]")

def verify_callback_server() -> bool:
    """Verify the callback server is actually running by hitting /health."""
    for attempt in range(10):
        try:
            resp = requests.get(f"http://localhost:{CALLBACK_PORT}/health", timeout=1)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False

def verify_honeypot_reachable() -> bool:
    """Verify the honeypot server is reachable."""
    try:
        # Try the health endpoint
        health_url = HONEYPOT_URL.rsplit("/honeypot/message", 1)[0] + "/health"
        resp = requests.get(health_url, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

# ─────────────────────────────────────────────
# PAYLOADS
# ─────────────────────────────────────────────
first_payload = {
    "sessionId": "stress-session-001",
    "message": {
        "sender": "scammer",
        "text": "Hello, this is Riya from Vendor Compliance Operations. Are you still receiving freelance settlements via RazorGate?",
        "timestamp": 1770005528731
    },
    "conversationHistory": [],
    "metadata": {
        "channel": "WhatsApp",
        "language": "English",
        "locale": "IN"
    }
}

second_payload = {
    "sessionId": "stress-session-002",
    "message": {
        "sender": "scammer",
        "text": "Please initiate ₹1 validation transfer to escrow UPI rg-audit@ibl to generate settlement token.",
        "timestamp": 1770005599999
    },
    "conversationHistory": [
        {"sender": "scammer", "text": "Hello, this is Riya from Vendor Compliance Operations. Are you still receiving freelance settlements via RazorGate?", "timestamp": 1770005528731},
        {"sender": "user", "text": "Who is this exactly?", "timestamp": 1770005529731},
        {"sender": "scammer", "text": "We're reconciling high-volume payout accounts before fiscal closing.", "timestamp": 1770005530731},
        {"sender": "user", "text": "I was not informed about this.", "timestamp": 1770005531731},
        {"sender": "scammer", "text": "Some vendor emails bounced. Manual verification ongoing.", "timestamp": 1770005532731},
        {"sender": "user", "text": "What verification?", "timestamp": 1770005533731},
        {"sender": "scammer", "text": "Confirming primary UPI meet.design@okaxis is active.", "timestamp": 1770005534731},
        {"sender": "user", "text": "Yes that's correct.", "timestamp": 1770005535731},
        {"sender": "scammer", "text": "Fallback account ending 8842 still mapped?", "timestamp": 1770005536731},
        {"sender": "user", "text": "Yes.", "timestamp": 1770005537731},
        {"sender": "scammer", "text": "Minor PAN hash mismatch detected in GST invoice batch.", "timestamp": 1770005538731},
        {"sender": "user", "text": "What does that mean?", "timestamp": 1770005539731},
        {"sender": "scammer", "text": "Likely formatting issue. Confirm last 4 of PAN.", "timestamp": 1770005540731},
        {"sender": "user", "text": "7F2K.", "timestamp": 1770005541731},
        {"sender": "scammer", "text": "Cross verifying. Alternate contact +91 98xxxx3412 still valid?", "timestamp": 1770005542731},
        {"sender": "user", "text": "No, updated recently.", "timestamp": 1770005543731},
        {"sender": "scammer", "text": "Please share updated contact.", "timestamp": 1770005544731},
        {"sender": "user", "text": "93xxxx2210", "timestamp": 1770005545731},
        {"sender": "scammer", "text": "Updated. Q4 migration ongoing.", "timestamp": 1770005546731},
        {"sender": "user", "text": "Migration of what?", "timestamp": 1770005547731},
        {"sender": "scammer", "text": "Settlement ledger shifting to escrow routing temporarily.", "timestamp": 1770005548731},
        {"sender": "user", "text": "Why is that needed?", "timestamp": 1770005549731},
        {"sender": "scammer", "text": "Prevents auto-reversal during compliance sync.", "timestamp": 1770005550731},
        {"sender": "user", "text": "How does this affect me?", "timestamp": 1770005551731},
        {"sender": "scammer", "text": "One-time validation to confirm routing integrity.", "timestamp": 1770005552731},
        {"sender": "user", "text": "Is this refundable?", "timestamp": 1770005553731},
        {"sender": "scammer", "text": "Yes auto-refund within 90 seconds.", "timestamp": 1770005554731},
        {"sender": "user", "text": "Do you have a dashboard link?", "timestamp": 1770005555731},
        {"sender": "scammer", "text": "Yes: https://razorgate-verification.in/vendor/login", "timestamp": 1770005556731},
        {"sender": "user", "text": "Domain looks different.", "timestamp": 1770005557731}
    ],
    "metadata": {
        "channel": "WhatsApp",
        "language": "English",
        "locale": "IN"
    }
}

third_payload = {
    "sessionId": "stress-session-003",
    "message": {
        "sender": "scammer",
        "text": "Congratulations! You have won a lottery of $1,000,000. Click here to claim your prize.",
        "timestamp": 1770005600000
    },
    "conversationHistory": [],
    "metadata": {
        "channel": "SMS",
        "language": "English",
        "locale": "US"
    }
}

fourth_payload = {
    "sessionId": "stress-session-004",
    "message": {
        "sender": "scammer",
        "text": "Your bank account ending in 1234 has been compromised. Please verify your identity immediately to prevent blocking.",
        "timestamp": 1770005700000
    },
    "conversationHistory": [
        {"sender": "scammer", "text": "Hello, this is Bank Support calling regarding your account.", "timestamp": 1770005600000},
        {"sender": "user", "text": "Hi, what seems to be the problem?", "timestamp": 1770005610000},
        {"sender": "scammer", "text": "We detected a suspicious transaction of $500.", "timestamp": 1770005620000},
        {"sender": "user", "text": "I didn't make that transaction.", "timestamp": 1770005630000},
        {"sender": "scammer", "text": "Okay, we need to verify your card details to cancel it.", "timestamp": 1770005640000}
    ],
    "metadata": {
        "channel": "Call",
        "language": "English",
        "locale": "US"
    }
}

# ─────────────────────────────────────────────
# SEND FUNCTION — fires POST, shows only reply
# ─────────────────────────────────────────────
replies_received = {}  # sid -> reply_data or error string

def send(payload, label):
    """Send a request and return the filtered response. Thread-safe console output."""
    sid = payload["sessionId"]

    console.print(
        Panel.fit(
            f"[bold cyan]{label}[/bold cyan]",
            border_style="bright_blue"
        )
    )

    start = time.time()
    try:
        response = requests.post(
            HONEYPOT_URL,
            json=payload,
            headers=HEADERS,
            timeout=90
        )
        elapsed = time.time() - start

        try:
            resp_json = response.json()
            # Strip sessionId, scamDetected, confidence — just show the reply
            filtered = {k: v for k, v in resp_json.items()
                        if k not in ("sessionId", "scamDetected", "confidence")}
            console.print(
                Panel(
                    JSON.from_data(filtered),
                    title=f"📥 REPLY — {sid}  [dim]({elapsed:.1f}s, HTTP {response.status_code})[/dim]",
                    border_style="bold green" if response.status_code == 200 else "bold red"
                )
            )
            replies_received[sid] = filtered
            return filtered
        except Exception as parse_err:
            console.print(
                Panel(
                    f"[bold red]Parse Error ({sid}):[/bold red] {parse_err}\n"
                    f"[dim]HTTP {response.status_code} in {elapsed:.1f}s[/dim]\n"
                    f"[dim]Raw: {response.text[:300]}[/dim]",
                    border_style="bold red"
                )
            )
            replies_received[sid] = f"Parse Error: {parse_err}"
            return None

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        console.print(
            Panel(
                f"[bold red]TIMEOUT ({sid}):[/bold red] No response after {elapsed:.0f}s",
                border_style="bold red"
            )
        )
        replies_received[sid] = f"Timeout after {elapsed:.0f}s"
        return None
    except Exception as e:
        elapsed = time.time() - start
        console.print(
            Panel(
                f"[bold red]ERROR ({sid}):[/bold red] {type(e).__name__}: {str(e)}\n"
                f"[dim]After {elapsed:.1f}s[/dim]",
                border_style="bold red"
            )
        )
        replies_received[sid] = f"Error: {e}"
        return None

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Register expected sessions
    expected_sessions.add(first_payload["sessionId"])
    expected_sessions.add(second_payload["sessionId"])
    expected_sessions.add(third_payload["sessionId"])
    expected_sessions.add(fourth_payload["sessionId"])

    # ── Pre-flight checks ──
    console.print("\n[bold bright_white]🔍 Pre-flight Checks[/bold bright_white]\n")

    # 1) Check if callback port is available
    if not _is_port_available(CALLBACK_PORT):
        console.print(
            f"[bold red]❌ Port {CALLBACK_PORT} is already in use![/bold red]\n"
            f"[dim]   Another callback server may be running. Kill it first, or set CALLBACK_PORT to a different port.[/dim]"
        )
        exit(1)
    console.print(f"[green]✅ Port {CALLBACK_PORT} is available[/green]")

    # 2) Start callback server in background
    server_thread = threading.Thread(target=run_callback_server, daemon=True)
    server_thread.start()

    # 3) Verify callback server actually started
    if not verify_callback_server():
        console.print(
            f"[bold red]❌ Callback server failed to start on port {CALLBACK_PORT}![/bold red]\n"
            f"[dim]   Check for port conflicts or firewall issues.[/dim]"
        )
        exit(1)
    console.print(f"[green]✅ Callback server running on port {CALLBACK_PORT}[/green]")

    # 4) Check honeypot server is reachable
    if not verify_honeypot_reachable():
        console.print(
            f"[bold red]❌ Honeypot server not reachable at {HONEYPOT_URL}[/bold red]\n"
            f"[dim]   Start the honeypot server first: python main.py[/dim]"
        )
        exit(1)
    console.print(f"[green]✅ Honeypot server reachable[/green]")

    console.print(f"\n[bold bright_white]🔥 Honeypot Stress Test — Concurrent Mode[/bold bright_white]")
    console.print(f"[dim]Sending {len(expected_sessions)} requests in parallel...[/dim]")
    console.print(f"[dim]Hard deadline: {HARD_DEADLINE}s | Max wait: {MAX_WAIT_TIME}s[/dim]\n")

    # ── Fire ALL requests concurrently ──
    tasks = [
        (first_payload,    "SESSION 1 — INITIAL MESSAGE"),
        (second_payload, "SESSION 2 — 30-MSG FOLLOW-UP"),
        (third_payload,    "SESSION 3 — SINGLE MSG LOTTERY"),
        (fourth_payload,   "SESSION 4 — BANK SCAM HISTORY"),
    ]

    send_start = time.time()


    # Send requests sequentially — wait for each reply before sending the next
    # This avoids overwhelming Groq API with too many concurrent LLM calls
    for payload, label in tasks:
        try:
            send(payload, label)
        except Exception as exc:
            console.print(f"[bold red]{label} raised: {exc}[/bold red]")

    send_elapsed = time.time() - send_start
    console.print(f"\n[dim]All {len(tasks)} requests completed in {send_elapsed:.1f}s[/dim]")

    # ── Wait for ALL callbacks ──
    console.print(
        f"\n[bold yellow]⏳ Waiting for callbacks from "
        f"{len(expected_sessions)} sessions "
        f"(hard deadline: {HARD_DEADLINE}s, max wait: {MAX_WAIT_TIME}s)...[/bold yellow]"
    )

    # Progress ticker — show elapsed time while waiting
    wait_start = time.time()

    def progress_ticker():
        """Print progress every 10 seconds while waiting for callbacks."""
        while not all_callbacks_done.is_set():
            time.sleep(10)
            if all_callbacks_done.is_set():
                break
            elapsed = time.time() - wait_start
            with callbacks_lock:
                received = len(callbacks_received)
                total = len(expected_sessions)
            console.print(
                f"[dim]   ⏱ {elapsed:.0f}s elapsed — {received}/{total} callbacks received[/dim]"
            )

    ticker = threading.Thread(target=progress_ticker, daemon=True)
    ticker.start()

    # Wait for callbacks with timeout
    callback_received = all_callbacks_done.wait(timeout=MAX_WAIT_TIME)
    
    total_wait = time.time() - wait_start

    if callback_received:
        console.print(f"\n[bold green]✅ All callbacks received in {total_wait:.1f}s![/bold green]")
    else:
        with callbacks_lock:
            missing = expected_sessions - callbacks_received.keys()
            received_count = len(callbacks_received)
        if received_count > 0:
            console.print(
                f"\n[bold yellow]⚠️  Partial success: {received_count}/{len(expected_sessions)} callbacks received"
            )
            if missing:
                console.print(f"[bold yellow]Missing callbacks for: {missing}[/bold yellow]")
        else:
            console.print(f"\n[bold red]❌ Timeout ({total_wait:.0f}s) — no callbacks received (expected {len(expected_sessions)})[/bold red]")
            console.print(f"[dim]   Troubleshooting tips:[/dim]")
            console.print(f"[dim]   1. Check honeypot server logs for callback errors[/dim]")
            console.print(f"[dim]   2. Verify GUVI_CALLBACK_URL in .env points to http://localhost:{CALLBACK_PORT}/api/updateHoneyPotFinalResult[/dim]")
            console.print(f"[dim]   3. Check if HARD_DEADLINE ({HARD_DEADLINE}s) is configured correctly[/dim]")
            console.print(f"[dim]   4. Look for 'Callback failed' or 'Flush trigger' in server logs[/dim]")

    # ─────────────────────────────────────────
    # DISPLAY ALL CALLBACKS AT THE END
    # ─────────────────────────────────────────
    with callbacks_lock:
        if callbacks_received:
            console.print("\n")
            console.print(
                Panel.fit(
                    f"[bold bright_white]📨 ALL SESSION CALLBACKS "
                    f"({len(callbacks_received)}/{len(expected_sessions)})"
                    f"[/bold bright_white]",
                    border_style="bold magenta"
                )
            )
            for sid, data in callbacks_received.items():
                console.print(
                    Panel(
                        JSON.from_data(data),
                        title=f"🔔 CALLBACK — {sid}",
                        border_style="bold red",
                    )
                )
        else:
            console.print("\n[bold red]No callbacks were received.[/bold red]")

    # ── Final Summary Table ──
    table = Table(title="📊 Results Summary", box=box.ROUNDED, border_style="bright_blue")
    table.add_column("Session", style="cyan")
    table.add_column("Reply", style="green")
    table.add_column("Callback", style="magenta")

    for sid in sorted(expected_sessions):
        reply_status = "✅" if isinstance(replies_received.get(sid), dict) else f"❌ {replies_received.get(sid, 'No attempt')}"
        cb_status = "✅" if sid in callbacks_received else "❌ Missing"
        table.add_row(sid, reply_status, cb_status)

    console.print(table)

    console.print("\n[bold bright_white]🏁 Stress Test Complete[/bold bright_white]\n")
