"""
Test Script for Agentic Honeypot API
Updated for PRD-aligned POST /honeypot/message endpoint.
"""

import asyncio
import json
import httpx
from datetime import datetime, timezone
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "hp_live_9fA3kLQxP2Z8R7sM1"


class HoneypotTester:
    """Test client for the Honeypot API."""
    
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY):
        self.base_url = base_url
        self.api_key = api_key
        self.client: Optional[httpx.AsyncClient] = None
        self.session_id_counter = 0
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
        return self
    
    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()
    
    def _get_headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _gen_session_id(self) -> str:
        self.session_id_counter += 1
        return f"test-session-{self.session_id_counter}-{datetime.now().strftime('%H%M%S')}"
    
    async def health_check(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            console.print(f"[red]Health check failed: {e}[/red]")
            return False
    
    async def send_message(
        self, 
        message: str, 
        session_id: Optional[str] = None,
        conversation_history: list = None,
        channel: str = "SMS"
    ) -> dict:
        """Send a message to POST /honeypot/message."""
        if session_id is None:
            session_id = self._gen_session_id()
        
        payload = {
            "sessionId": session_id,
            "message": {
                "sender": "scammer",
                "text": message,
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            },
            "conversationHistory": conversation_history or [],
            "metadata": {
                "channel": channel,
                "language": "English",
                "locale": "IN"
            }
        }
        
        response = await self.client.post(
            f"{self.base_url}/honeypot/message",
            json=payload,
            headers=self._get_headers()
        )
        
        return response.json()


# Sample scam messages for testing
SCAM_MESSAGES = [
    {
        "name": "Bank Block Scam",
        "message": "Dear Customer, Your SBI account will be blocked today due to incomplete KYC. Update immediately: http://sbi-verify.xyz/update",
        "expected_scam": True
    },
    {
        "name": "UPI Verification",
        "message": "URGENT: Your UPI ID has been suspended. Share OTP received on your mobile to verify and restore access immediately.",
        "expected_scam": True
    },
    {
        "name": "Lottery Winner",
        "message": "Congratulations! You have won Rs. 50,00,000 in Jio Lucky Draw. Call +91-9876543210 to claim your prize. Share your bank details.",
        "expected_scam": True
    },
    {
        "name": "IT Refund",
        "message": "Income Tax Department: Your ITR refund of Rs. 25,430 is pending. Click here to claim: bit.ly/itrefund2024. Hurry, expires today!",
        "expected_scam": True
    },
    {
        "name": "KYC Update",
        "message": "Your Paytm wallet will be blocked in 24 hours. Complete KYC update now by sending Aadhar photo and PAN card to verify@paytm.xyz",
        "expected_scam": True
    },
    {
        "name": "Police Threat",
        "message": "This is Cyber Crime Police. A case has been registered against your Aadhar number. Call 089XXXXXXXX immediately to avoid arrest.",
        "expected_scam": True
    },
    {
        "name": "Legitimate Meeting",
        "message": "Hi, just confirming our meeting tomorrow at 3 PM. Please bring the project documents. See you then!",
        "expected_scam": False
    },
    {
        "name": "Order Delivery",
        "message": "Your Amazon order has been shipped! Track your package with order ID #12345. Expected delivery: Jan 28, 2024.",
        "expected_scam": False
    },
    {
        "name": "Cashback Offer",
        "message": "ICICI Alert: You have earned Rs 500 cashback! To redeem, share your debit card CVV and OTP. Offer valid today only!",
        "expected_scam": True
    },
    {
        "name": "Account Frozen",
        "message": "RBI Notice: Your bank account has been frozen due to suspicious activity. Share your UPI PIN to unfreeze: scammer@ybl",
        "expected_scam": True
    }
]


async def run_single_message_tests(tester: HoneypotTester):
    """Run tests with individual scam messages."""
    console.print(Panel("[bold cyan]🧪 SINGLE MESSAGE TESTS[/bold cyan]"))
    
    results_table = Table(title="Test Results")
    results_table.add_column("Test Case", style="cyan")
    results_table.add_column("Expected", justify="center")
    results_table.add_column("Detected", justify="center")
    results_table.add_column("Confidence", justify="right")
    results_table.add_column("Reply Preview", style="dim", max_width=40)
    results_table.add_column("Status", justify="center")
    
    passed = 0
    failed = 0
    
    for test in SCAM_MESSAGES:
        console.print(f"\n[bold]Testing:[/bold] {test['name']}")
        console.print(f"[dim]{test['message'][:80]}...[/dim]")
        
        try:
            result = await tester.send_message(test["message"])
            
            detected = result.get("scamDetected", False)
            confidence = result.get("confidence", 0)
            reply = result.get("reply", "")
            
            is_correct = detected == test["expected_scam"]
            
            if is_correct:
                passed += 1
                status_cell = "[green]✅ PASS[/green]"
            else:
                failed += 1
                status_cell = "[red]❌ FAIL[/red]"
            
            results_table.add_row(
                test["name"],
                "🚨 Scam" if test["expected_scam"] else "✅ Safe",
                "🚨 Scam" if detected else "✅ Safe",
                f"{confidence:.0%}",
                reply[:40] + "..." if len(reply) > 40 else reply,
                status_cell
            )
            
            if detected and reply:
                console.print(f"[green]Agent Reply:[/green] {reply}")
            
            await asyncio.sleep(1)  # Rate limiting
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            failed += 1
            results_table.add_row(
                test["name"], "—", "ERROR", "—", "—", "[red]❌ ERROR[/red]"
            )
    
    console.print("\n")
    console.print(results_table)
    console.print(f"\n[bold]Results:[/bold] {passed} passed, {failed} failed")
    
    return passed, failed


async def run_multi_turn_test(tester: HoneypotTester):
    """Test multi-turn conversation handling."""
    console.print(Panel("[bold cyan]🔄 MULTI-TURN CONVERSATION TEST[/bold cyan]"))
    
    session_id = tester._gen_session_id()
    history = []
    
    scammer_messages = [
        "Your bank account will be blocked today. Verify immediately.",
        "Due to incomplete KYC verification. Share your Aadhar and PAN to update.",
        "I am from SBI customer care. Send documents to verify@sbi.xyz or share OTP received on your mobile.",
    ]
    
    for i, msg in enumerate(scammer_messages):
        console.print(f"\n[bold red]Scammer ({i+1}):[/bold red] {msg}")
        
        result = await tester.send_message(
            message=msg,
            session_id=session_id,
            conversation_history=history
        )
        
        reply = result.get("reply", "")
        if reply:
            console.print(f"[bold green]Agent:[/bold green] {reply}")
            history.append({"sender": "agent", "text": reply, "timestamp": datetime.now(timezone.utc).isoformat()})
        
        history.append({"sender": "scammer", "text": msg, "timestamp": datetime.now(timezone.utc).isoformat()})
        
        console.print(f"  Scam: {result.get('scamDetected')}, Confidence: {result.get('confidence', 0):.0%}")
        
        await asyncio.sleep(1)
    
    console.print(f"\n[bold]Session {session_id} — {len(history)} messages exchanged[/bold]")


async def main():
    """Run all tests."""
    console.print("\n" + "=" * 70)
    console.print("[bold magenta]🍯 AGENTIC HONEYPOT — TEST SUITE (PRD v2)[/bold magenta]")
    console.print("=" * 70)
    
    async with HoneypotTester() as tester:
        console.print("\n[bold]Checking API health...[/bold]")
        if not await tester.health_check():
            console.print("[bold red]❌ API is not running! Start with: python main.py[/bold red]")
            return
        
        console.print("[bold green]✅ API is healthy![/bold green]\n")
        
        # 1. Single message tests
        passed, failed = await run_single_message_tests(tester)
        
        # 2. Multi-turn test
        await run_multi_turn_test(tester)
        
        # Summary
        console.print("\n" + "=" * 70)
        console.print(f"[bold magenta]📊 SUMMARY: {passed} passed, {failed} failed[/bold magenta]")
        console.print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
