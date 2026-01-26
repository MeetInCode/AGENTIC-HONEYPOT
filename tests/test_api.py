"""
Test Script for Agentic Honeypot API
Comprehensive testing with sample scam messages.
"""

import asyncio
import json
import httpx
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "your-secret-api-key-here"  # Match with .env


class HoneypotTester:
    """Test client for the Honeypot API."""
    
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY):
        self.base_url = base_url
        self.api_key = api_key
        self.client: Optional[httpx.AsyncClient] = None
        self.session_id_counter = 0
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
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
        """Check if API is healthy."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            console.print(f"[red]Health check failed: {e}[/red]")
            return False
    
    async def analyze_message(
        self, 
        message: str, 
        session_id: Optional[str] = None,
        conversation_history: list = None,
        channel: str = "SMS"
    ) -> dict:
        """Send a message for analysis."""
        if session_id is None:
            session_id = self._gen_session_id()
        
        payload = {
            "sessionId": session_id,
            "message": {
                "sender": "scammer",
                "text": message,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            },
            "conversationHistory": conversation_history or [],
            "metadata": {
                "channel": channel,
                "language": "English",
                "locale": "IN"
            }
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/analyze",
            json=payload,
            headers=self._get_headers()
        )
        
        return response.json()
    
    async def get_session(self, session_id: str) -> dict:
        """Get session details."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/session/{session_id}",
            headers=self._get_headers()
        )
        return response.json()
    
    async def list_sessions(self) -> dict:
        """List all sessions."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/sessions",
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

# Multi-turn conversation test
MULTI_TURN_CONVERSATION = [
    {
        "sender": "scammer",
        "text": "Your bank account will be blocked today. Verify immediately."
    },
    {
        "sender": "user", 
        "text": "Why will my account be blocked?"
    },
    {
        "sender": "scammer",
        "text": "Due to incomplete KYC verification. Share your Aadhar and PAN to update."
    },
    {
        "sender": "user",
        "text": "How do I share? Which bank are you from?"
    },
    {
        "sender": "scammer",
        "text": "I am from SBI customer care. Send documents to verify@sbi.xyz or share OTP received on your mobile."
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
    results_table.add_column("Status", justify="center")
    
    passed = 0
    failed = 0
    
    for test in SCAM_MESSAGES:
        console.print(f"\n[bold]Testing:[/bold] {test['name']}")
        console.print(f"[dim]{test['message'][:80]}...[/dim]")
        
        try:
            result = await tester.analyze_message(test["message"])
            
            detected = result.get("scamDetected", False)
            confidence = 0
            if result.get("councilVerdict"):
                confidence = result["councilVerdict"].get("confidence", 0)
            
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
                status_cell
            )
            
            # Show agent response if scam
            if detected and result.get("agentResponse"):
                console.print(f"[green]Agent Response:[/green] {result['agentResponse']}")
            
            await asyncio.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            failed += 1
            results_table.add_row(
                test["name"],
                "🚨 Scam" if test["expected_scam"] else "✅ Safe",
                "ERROR",
                "-",
                "[red]❌ ERROR[/red]"
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
    
    for i, turn in enumerate(MULTI_TURN_CONVERSATION):
        if turn["sender"] == "scammer":
            console.print(f"\n[bold red]Scammer ({i+1}):[/bold red] {turn['text']}")
            
            result = await tester.analyze_message(
                message=turn["text"],
                session_id=session_id,
                conversation_history=history
            )
            
            if result.get("agentResponse"):
                console.print(f"[bold green]Agent:[/bold green] {result['agentResponse']}")
                # Add agent response to history for next turn
                history.append({
                    "sender": "user",
                    "text": result["agentResponse"],
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
            
            # Show extracted intelligence
            intel = result.get("extractedIntelligence", {})
            if any(intel.get(k) for k in ["upiIds", "phoneNumbers", "phishingLinks"]):
                console.print(f"[yellow]Intel extracted: {json.dumps(intel, indent=2)}[/yellow]")
        
        # Add scammer message to history
        history.append({
            "sender": turn["sender"],
            "text": turn["text"],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        
        await asyncio.sleep(0.5)
    
    # Get final session state
    session = await tester.get_session(session_id)
    console.print(f"\n[bold]Final Session State:[/bold]")
    console.print(f"  Total Messages: {session.get('total_messages', 0)}")
    console.print(f"  Scam Detected: {session.get('is_scam_detected', False)}")
    console.print(f"  Callback Sent: {session.get('callback_sent', False)}")
    
    return session_id


async def run_intelligence_extraction_test(tester: HoneypotTester):
    """Test intelligence extraction capabilities."""
    console.print(Panel("[bold cyan]🔍 INTELLIGENCE EXTRACTION TEST[/bold cyan]"))
    
    test_messages = [
        "Send money to scammer@ybl for verification. Contact +91-9876543210 for details.",
        "Visit http://fake-bank.xyz/verify and enter your account number 1234567890123456",
        "Transfer Rs 5000 to 9988776655@paytm and send screenshot to verify@scam.com",
    ]
    
    for msg in test_messages:
        console.print(f"\n[bold]Message:[/bold] {msg}")
        
        result = await tester.analyze_message(msg)
        intel = result.get("extractedIntelligence", {})
        
        console.print("[bold yellow]Extracted Intelligence:[/bold yellow]")
        if intel.get("upiIds"):
            console.print(f"  📱 UPI IDs: {intel['upiIds']}")
        if intel.get("phoneNumbers"):
            console.print(f"  📞 Phone Numbers: {intel['phoneNumbers']}")
        if intel.get("phishingLinks"):
            console.print(f"  🔗 Phishing Links: {intel['phishingLinks']}")
        if intel.get("bankAccounts"):
            console.print(f"  🏦 Bank Accounts: {intel['bankAccounts']}")
        if intel.get("emailAddresses"):
            console.print(f"  📧 Emails: {intel['emailAddresses']}")
        if intel.get("suspiciousKeywords"):
            console.print(f"  ⚠️ Keywords: {intel['suspiciousKeywords'][:5]}")
        
        await asyncio.sleep(0.5)


async def main():
    """Run all tests."""
    console.print("\n" + "=" * 70)
    console.print("[bold magenta]🍯 AGENTIC HONEYPOT - TEST SUITE[/bold magenta]")
    console.print("=" * 70)
    
    async with HoneypotTester() as tester:
        # Health check
        console.print("\n[bold]Checking API health...[/bold]")
        if not await tester.health_check():
            console.print("[bold red]❌ API is not running! Start the server first.[/bold red]")
            console.print("[dim]Run: python main.py[/dim]")
            return
        
        console.print("[bold green]✅ API is healthy![/bold green]")
        
        # Run tests
        console.print("\n")
        
        # 1. Single message tests
        passed, failed = await run_single_message_tests(tester)
        
        # 2. Multi-turn conversation test
        await run_multi_turn_test(tester)
        
        # 3. Intelligence extraction test
        await run_intelligence_extraction_test(tester)
        
        # Summary
        console.print("\n" + "=" * 70)
        console.print("[bold magenta]📊 TEST SUMMARY[/bold magenta]")
        console.print("=" * 70)
        
        sessions = await tester.list_sessions()
        console.print(f"  Active Sessions: {sessions.get('active_sessions', 0)}")
        console.print(f"  Single Message Tests: {passed} passed, {failed} failed")
        console.print("\n[bold green]✅ All tests completed![/bold green]\n")


if __name__ == "__main__":
    asyncio.run(main())
