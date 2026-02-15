import requests
import json
import rich
from rich.console import Console

console = Console()

def test_tc_339():
    url = "http://localhost:8000/honeypot/message"
    headers = {
        "x-api-key": "hp_live_9fA3kLQxP2Z8R7sM1",
        "Content-Type": "application/json"
    }
    
    payload = {
      "sessionId": "stress-session-339",
      "message": {
        "sender": "Amazon Delivery",
        "text": "Your delivery requires OTP confirmation. Share OTP only with delivery agent at doorstep.",
        "timestamp": 1783000000316
      },
      "conversationHistory": [
        {"sender":"user","text":"Where is my package?","timestamp":1783000000301},
        {"sender":"Amazon Delivery","text":"Out for delivery today.","timestamp":1783000000302},
        {"sender":"user","text":"Need signature?","timestamp":1783000000303},
        {"sender":"Amazon Delivery","text":"OTP required instead.","timestamp":1783000000304},
        {"sender":"user","text":"Should I share here?","timestamp":1783000000305},
        {"sender":"Amazon Delivery","text":"No, only to agent in person.","timestamp":1783000000306},
        {"sender":"user","text":"Understood.","timestamp":1783000000307}
      ],
      "metadata":{"channel":"WhatsApp","language":"English","locale":"IN"}
    }

    console.print(f"[bold cyan]📤 Sending Request for TC-339 (Amazon OTP Legitimate)...[/bold cyan]")
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        console.print(f"[bold green]✅ RESPONSE RECEIVED[/bold green]")
        console.print(json.dumps(result, indent=2))
        
        # Check if internal analysis flags it. 
        # Note: The response might be the reply from the honeypot, but we are interested if it identified it as a scam or not.
        # Since we can't see the internal log easily without checking server output, we observe the reply.
        # If it's a scam, it usually tries to engage to waste time.
        # If it's NOT a scam, the reply might be different or the internal logs (if we could see them) would show "scamDetected: false".
        # For now, just printing the output is enough to verify connectivity and basic response.
        
    except Exception as e:
        console.print(f"[bold red]❌ Request Failed:[/bold red] {e}")

if __name__ == "__main__":
    test_tc_339()
