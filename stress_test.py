import requests
import time
import threading
import uvicorn
import socket
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, Request
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
from rich.table import Table
from rich import box
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
HONEYPOT_URL = os.getenv("HONEYPOT_URL", "http://localhost:8000/honeypot/message")
CALLBACK_PORT = int(os.getenv("CALLBACK_PORT", "8001"))
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "hp_live_9fA3kLQxP2Z8R7sM1")
MAX_WAIT_TIME = int(os.getenv("MAX_CALLBACK_WAIT", "60"))

HEADERS = {
    "x-api-key": API_SECRET_KEY,
    "Content-Type": "application/json"
}

console = Console()

# ─────────────────────────────────────────────
# CALLBACK SERVER
# ─────────────────────────────────────────────
app = FastAPI()

callbacks_received = {}
expected_sessions = set()
callbacks_lock = threading.Lock()
all_done = threading.Event()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/updateHoneyPotFinalResult")
async def callback(request: Request):
    payload = await request.json()
    sid = payload.get("sessionId")

    console.print(
        Panel(
            JSON.from_data(payload),
            title=f"🔔 CALLBACK — {sid}",
            border_style="bold magenta"
        )
    )

    with callbacks_lock:
        callbacks_received[sid] = payload
        if expected_sessions == callbacks_received.keys():
            all_done.set()

    return {"status": "ok"}

def run_callback_server():
    uvicorn.run(app, host="0.0.0.0", port=CALLBACK_PORT, log_level="warning")

# ─────────────────────────────────────────────
# TEST CASES (ADD YOUR 30 HERE)
# ─────────────────────────────────────────────

TEST_CASES = [
    # Example minimal case
    {
        "sessionId": "demo-session-001",
        "message": {
            "sender": "scammer",
            "text": "Airtel Notice: SIM will deactivate. Update KYC now: https://airtel-kycverify.co.in",
            "timestamp": 1770030000001
        },
        "conversationHistory": [],
        "metadata": {"channel": "SMS", "language": "English", "locale": "IN"}
    },
    {
    "sessionId": "stress-session-131",
    "message": {
        "sender": "scammer",
        "text": "Please confirm the OTP sent to your registered mobile to block the transaction.",
        "timestamp": 1770020000016
    },
    "conversationHistory": [
        {"sender": "scammer", "text": "HDFC Bank Fraud Prevention Desk.", "timestamp": 1770020000001},
        {"sender": "scammer", "text": "We detected ₹24,890 spent at Amazon India.", "timestamp": 1770020000002},
        {"sender": "user", "text": "I didn't make that purchase.", "timestamp": 1770020000003},
        {"sender": "scammer", "text": "No problem, we'll cancel it immediately.", "timestamp": 1770020000004},
        {"sender": "scammer", "text": "For security, confirm your date of birth.", "timestamp": 1770020000005},
        {"sender": "user", "text": "12 July 1999", "timestamp": 1770020000006},
        {"sender": "scammer", "text": "Thank you. Last 4 digits of your card please?", "timestamp": 1770020000007},
        {"sender": "user", "text": "4432", "timestamp": 1770020000008},
        {"sender": "scammer", "text": "Transaction is still in processing state.", "timestamp": 1770020000009},
        {"sender": "scammer", "text": "We are placing a temporary block.", "timestamp": 1770020000010},
        {"sender": "user", "text": "Okay.", "timestamp": 1770020000011},
        {"sender": "scammer", "text": "You will receive an OTP for cancellation.", "timestamp": 1770020000012},
        {"sender": "user", "text": "Yes I got something.", "timestamp": 1770020000013},
        {"sender": "scammer", "text": "Please share quickly before it expires.", "timestamp": 1770020000014},
        {"sender": "user", "text": "It says do not share OTP.", "timestamp": 1770020000015}
    ],
    "metadata": {"channel": "WhatsApp", "language": "English", "locale": "IN"}
},{
    "sessionId": "stress-session-133",
    "message": {
        "sender": "scammer",
        "text": "To dispute this $499 charge, reply with your full name and call the number provided immediately.",
        "timestamp": 1770020000218
    },
    "conversationHistory": [
        {"sender": "scammer", "text": "PayPal Invoice #77421", "timestamp": 1770020000201},
        {"sender": "scammer", "text": "Amount: $499.00", "timestamp": 1770020000202},
        {"sender": "scammer", "text": "Merchant: Norton Security Services", "timestamp": 1770020000203},
        {"sender": "user", "text": "I didn't order this subscription.", "timestamp": 1770020000204},
        {"sender": "scammer", "text": "Thank you for contacting PayPal Resolution Center.", "timestamp": 1770020000205},
        {"sender": "scammer", "text": "We will assist you in reversing this charge.", "timestamp": 1770020000206},
        {"sender": "scammer", "text": "Please confirm billing ZIP code.", "timestamp": 1770020000207},
        {"sender": "user", "text": "94107", "timestamp": 1770020000208},
        {"sender": "scammer", "text": "We have flagged this as suspicious.", "timestamp": 1770020000209},
        {"sender": "scammer", "text": "Charge is still pending settlement.", "timestamp": 1770020000210},
        {"sender": "user", "text": "Can you cancel it?", "timestamp": 1770020000211},
        {"sender": "scammer", "text": "Yes but requires identity verification.", "timestamp": 1770020000212},
        {"sender": "scammer", "text": "Kindly confirm date of birth.", "timestamp": 1770020000213},
        {"sender": "user", "text": "Jan 14 1995", "timestamp": 1770020000214},
        {"sender": "scammer", "text": "Thank you for verification.", "timestamp": 1770020000215},
        {"sender": "scammer", "text": "Dispute form link attached.", "timestamp": 1770020000216},
        {"sender": "user", "text": "The link looks unusual.", "timestamp": 1770020000217}
    ],
    "metadata": {"channel": "Email", "language": "English", "locale": "US"}
}
]

# ─────────────────────────────────────────────
# SEND FUNCTION
# ─────────────────────────────────────────────
def send_request(payload):
    sid = payload["sessionId"]

    console.print(
        Panel(
            JSON.from_data(payload),
            title=f"📤 REQUEST — {sid}",
            border_style="bright_blue"
        )
    )

    try:
        resp = requests.post(
            HONEYPOT_URL,
            json=payload,
            headers=HEADERS,
            timeout=90
        )

        data = resp.json()

        console.print(
            Panel(
                JSON.from_data(data),
                title=f"📥 REPLY — {sid}",
                border_style="green" if resp.status_code == 200 else "red"
            )
        )
        return sid, data

    except Exception as e:
        console.print(
            Panel(
                f"ERROR: {e}",
                title=f"❌ ERROR — {sid}",
                border_style="red"
            )
        )
        return sid, None

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":

    # Start callback server
    server_thread = threading.Thread(target=run_callback_server, daemon=True)
    server_thread.start()
    time.sleep(1)

    console.print("\n🔥 Honeypot Mass Testing Started\n")

    # Register expected sessions
    for case in TEST_CASES:
        expected_sessions.add(case["sessionId"])

    # ── PARALLEL sending (all requests at once) ──
    console.print(f"[bold yellow]⚡ Sending {len(TEST_CASES)} requests in PARALLEL...[/bold yellow]\n")
    t_start = time.time()

    with ThreadPoolExecutor(max_workers=len(TEST_CASES)) as executor:
        futures = {executor.submit(send_request, case): case["sessionId"] for case in TEST_CASES}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                future.result()
            except Exception as e:
                console.print(f"[red]Thread error for {sid}: {e}[/red]")

    t_sent = time.time() - t_start
    console.print(f"\n[bold green]✅ All {len(TEST_CASES)} requests sent in {t_sent:.2f}s[/bold green]")

    console.print("\n⏳ Waiting for callbacks...\n")
    all_done.wait(timeout=MAX_WAIT_TIME)

    # ─────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────
    table = Table(title="📊 Test Summary", box=box.ROUNDED)
    table.add_column("Session", style="cyan")
    table.add_column("Callback Received", style="magenta")

    for sid in expected_sessions:
        status = "✅" if sid in callbacks_received else "❌"
        table.add_row(sid, status)

    console.print(table)
    console.print("\n🏁 Testing Complete\n")