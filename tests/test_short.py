"""
Short Test Script for Agentic Honeypot API
Tests 1 scam case and 1 legitimate case.
"""

import asyncio
import httpx
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()
BASE_URL = "http://127.0.0.1:8000"
API_KEY = "hp_live_9fA3kLQxP2Z8R7sM1" 

async def test_scam_detection():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Headers
        headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}
        
        # Test Case 1: SCAM
        scam_msg = "Your SBI account is BLOCKED. Update KYC immediately or account will be suspended. Click: http://sbi-update.xyz"
        
        console.print("\n[bold cyan]🧪 Testing SCAM Message[/bold cyan]")
        console.print(f"Message: {scam_msg}")
        
        scam_payload = {
            "sessionId": f"test-scam-{datetime.now().strftime('%H%M%S')}",
            "message": {
                "sender": "scammer",
                "text": scam_msg,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        try:
            resp = await client.post(f"{BASE_URL}/api/v1/analyze", json=scam_payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                is_scam = data.get("scamDetected", False)
                confidence = data.get("councilVerdict", {}).get("confidence", 0)
                agent_reply = data.get("agentResponse", "No response")
                
                status_color = "green" if is_scam else "red"
                console.print(f"[{status_color}]Result: Detected as SCAM={is_scam} (Confidence: {confidence:.0%})[/{status_color}]")
                if is_scam:
                     console.print(f"[yellow]Agent Reply:[/yellow] {agent_reply}")
            else:
                console.print(f"[red]Error: {resp.status_code} - {resp.text}[/red]")
        except Exception as e:
            console.print(f"[red]Connection failed: {e}[/red]")

        # Test Case 2: LEGITIMATE
        legit_msg = "Hey, forgot my keys at the office. Can you check if they are on my desk?"
        
        console.print("\n[bold cyan]🧪 Testing LEGITIMATE Message[/bold cyan]")
        console.print(f"Message: {legit_msg}")
        
        legit_payload = {
            "sessionId": f"test-legit-{datetime.now().strftime('%H%M%S')}",
            "message": {
                "sender": "scammer", 
                "text": legit_msg,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        try:
            resp = await client.post(f"{BASE_URL}/api/v1/analyze", json=legit_payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                is_scam = data.get("scamDetected", False)
                confidence = data.get("councilVerdict", {}).get("confidence", 0)
                
                # We expect is_scam to be False
                status_color = "green" if not is_scam else "red"
                console.print(f"[{status_color}]Result: Detected as SCAM={is_scam} (Confidence: {confidence:.0%})[/{status_color}]")
            else:
                console.print(f"[red]Error: {resp.status_code} - {resp.text}[/red]")
        except Exception as e:
            console.print(f"[red]Connection failed: {e}[/red]")

if __name__ == "__main__":
    asyncio.run(test_scam_detection())
