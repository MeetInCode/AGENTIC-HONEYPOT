import requests
import time
import threading
import uvicorn
import os
from fastapi import FastAPI, Request
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
HONEYPOT_URL = os.getenv("HONEYPOT_URL", "http://localhost:8000/honeypot/message")
# Using 8002 to avoid conflict with main stress_test.py if it's lingering
CALLBACK_PORT = int(os.getenv("CALLBACK_PORT_2", "8002")) 
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "hp_live_9fA3kLQxP2Z8R7sM1")

HEADERS = {
    "x-api-key": API_SECRET_KEY,
    "Content-Type": "application/json"
}

console = Console()

# ─────────────────────────────────────────────
# CALLBACK SERVER
# ─────────────────────────────────────────────
app = FastAPI()

callbacks_received = []
callbacks_lock = threading.Lock()

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
            title=f"🔔 CALLBACK RECEIVED — {sid}",
            border_style="magenta"
        )
    )
    return {"status": "ok"}

def run_callback_server():
    # Only try to bind if needed, but for now we spin it up just in case
    # Ideally, we update .env GUVI_CALLBACK_URL if we want callbacks here.
    try:
        uvicorn.run(app, host="0.0.0.0", port=CALLBACK_PORT, log_level="error")
    except Exception as e:
        console.print(f"[red]Callback server failed to start: {e}[/red]")

# ─────────────────────────────────────────────
# SCENARIO DEFINITION
# ─────────────────────────────────────────────

SESSION_ID = "multi-turn-scenario-002"

PAYLOADS = [
    {
        "desc": "1. UPI Details",
        "text": "Hello, send ₹500 fee to payment@paytm immediately or account blocked."
    },
    {
        "desc": "2. Phone Number",
        "text": "Call out support team at +91 9876543210 for help."
    },
    {
        "desc": "3. Phishing Link",
        "text": "Verify your KYC here: http://fake-bank-kyc.com/verify now."
    },
    {
        "desc": "4. Threat/Urgency",
        "text": "Police complaint will be filed in 1 hour if you do not pay."
    }
]

def send_message(text, description):
    payload = {
        "sessionId": SESSION_ID,
        "message": {
            "sender": "scammer",
            "text": text,
            "timestamp": int(time.time() * 1000)
        },
        "conversationHistory": [], # Simplistic; real test might append
        "metadata": {
            "channel": "WhatsApp",
            "language": "English",
            "source": "stress_test_2"
        }
    }

    console.print(f"\n[bold blue]📤 SENDING: {description}[/bold blue]\nRequest: {text}")

    try:
        resp = requests.post(
            HONEYPOT_URL,
            json=payload,
            headers=HEADERS,
            timeout=120
        )
        
        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("reply", "No reply field")
            console.print(f"[green]✅ REPLY:[/green] {reply}\n")
        else:
            console.print(f"[red]❌ FAIL {resp.status_code}:[/red] {resp.text}\n")
            
    except Exception as e:
        console.print(f"[red]❌ EXCEPTION:[/red] {e}\n")

if __name__ == "__main__":
    # Start callback listener thread on 8002 just in case
    t = threading.Thread(target=run_callback_server, daemon=True)
    t.start()
    
    # Wait for server to be ready
    time.sleep(2)
    
    console.print(f"\n[bold yellow]🚀 STARTING MULTI-TURN TEST SCENARIO ({SESSION_ID})[/bold yellow]\n")

    for p in PAYLOADS:
        send_message(p["text"], p["desc"])
        time.sleep(5) # Wait between turns

    console.print("[bold green]🏁 TEST COMPLETE[/bold green]")
    # Keep alive for callbacks
    time.sleep(10)
