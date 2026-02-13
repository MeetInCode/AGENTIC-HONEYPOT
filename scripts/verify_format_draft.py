
import asyncio
import json
import logging
import uuid
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_format")

BASE_URL = "http://localhost:8000"

async def run_single_session():
    session_id = f"verify-format-{uuid.uuid4().hex[:8]}"
    
    # 1. Send specific scam trigger message
    msg = "I want to pay the registration fee. Send me your UPI ID (scammer@ybl) and bank account details (1234567890). And the link http://scam.com/pay"
    
    logger.info(f"Sending message to session {session_id}...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Send message
        resp = await client.post(
            f"{BASE_URL}/chat",
            json={"message": msg, "sessionId": session_id}
        )
        logger.info(f"Reply: {resp.json()}")
        
        # Wait for callback (simulated by polling or just waiting appropriately if we had a webhook, 
        # but here we rely on the server logs or we can mock the webhook receiver)
        
        # Since we can't easily capture the webhook locally without a server, 
        # we will rely on checking the logs or use the 'debug_specific_agents.py' approach 
        # but targeting the Orchestrator's internal state if possible, 
        # OR better: we just assume the server is printing the callback to stdout/logs.
        
        logger.info("Waiting 20 seconds for callback generation...")
        await asyncio.sleep(20)
        
        # In a real integration test we'd have a receiver. 
        # For now, we manually check the console output of the SERVER process 
        # which should print the callback JSON if DEBUG is on, 
        # or we rely on the previous stress test output which showed callbacks.
        
        # However, to see the content, we can use the '/internal/state' endpoint if it exists,
        # or just rely on the fact that I can't easily see the callback content 
        # without a receiving server.
        
        # ACTUALLY: The stress_test.py DOES print the callback.
        # Let's write a mini-server to receive the callback in this script.

from fastapi import FastAPI, Request
import uvicorn
import threading

app = FastAPI()

@app.post("/api/updateHoneyPotFinalResult")
async def receive_callback(request: Request):
    data = await request.json()
    print("\n\n👀 RECEIVED CALLBACK JSON 👀")
    print(json.dumps(data, indent=2))
    print("--------------------------------------------------\n")
    return {"status": "ok"}

def start_server():
    uvicorn.run(app, host="0.0.0.0", port=8001)

async def main():
    # Start callback receiver in background
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    
    # Update settings to point to our local receiver (dynamically if possible, 
    # but since settings are loaded at startup, we might need to restart main.py with env var)
    # OR we just rely on the existing 'stress_test.py' which essentially does this but cleaner.
    
    # Let's just use stress_test.py but modified to print the FULL JSON.
    pass

if __name__ == "__main__":
    pass
