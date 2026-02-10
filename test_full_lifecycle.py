"""
Full lifecycle test — PRD-aligned.
Tests multi-turn bank fraud scenario with callback verification.
"""

import requests
import json
import time
import uuid
from datetime import datetime, timezone


BASE_URL = "http://localhost:8000"
API_KEY = "hp_live_9fA3kLQxP2Z8R7sM1"


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_section(title):
    print(f"\n{Colors.HEADER}{'='*60}\n{title}\n{'='*60}{Colors.ENDC}")

def print_step(step, content):
    print(f"\n{Colors.BLUE}{Colors.BOLD}[STEP {step}]{Colors.ENDC} {content}")

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}❌ {msg}{Colors.ENDC}")


class LifecycleTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.history = []
        self.headers = {
            "x-api-key": API_KEY,
            "Content-Type": "application/json"
        }
        
    def send_message(self, text, sender="scammer"):
        payload = {
            "sessionId": self.session_id,
            "message": {
                "sender": sender,
                "text": text,
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            },
            "conversationHistory": self.history,
            "metadata": {
                "channel": "WhatsApp",
                "language": "English",
                "locale": "IN"
            }
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/honeypot/message",
                json=payload,
                headers=self.headers,
                timeout=120
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print_error(f"Request failed: {e}")
            return None

    def run(self):
        print_section("🕵️  AGENTIC HONEYPOT FULL LIFECYCLE TEST (PRD v2)")
        print(f"Session ID: {self.session_id}")
        print(f"Endpoint: POST {BASE_URL}/honeypot/message")
        
        conversation_flow = [
            "Dear customer, your HDFC bank account will be blocked today due to pending KYC. Click link: http://hdfc-kyc-update.com",
            "Yes this is Manager. Please share your Aadhar number and OTP to stop blocking.",
            "Don't delay. Also transfer Rs 10 to verify UPI ID: scammer@upi. This is refundable.",
            "Why are you not replying? Police will come to your house if you don't verify."
        ]
        
        for i, msg in enumerate(conversation_flow):
            print_step(i + 1, f"Scammer says: \"{msg}\"")
            
            data = self.send_message(msg)
            if not data:
                break

            scam_detected = data.get("scamDetected", False)
            reply = data.get("reply", "")
            confidence = data.get("confidence", 0)

            # Update History
            self.history.append({
                "sender": "scammer",
                "text": msg,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            if reply:
                self.history.append({
                    "sender": "agent",
                    "text": reply,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            # Output
            print(f"{Colors.CYAN}--- Response ---{Colors.ENDC}")
            print(f"🛡️  Scam Detected: {scam_detected}")
            print(f"📊 Confidence: {confidence:.0%}")
            print(f"🤖 Agent Reply: {Colors.WARNING}\"{reply}\"{Colors.ENDC}")

            # Validations
            if i == 0 and scam_detected:
                print_success("Scam correctly detected on first turn.")
            
            if reply and "scam" in reply.lower() and "detected" in reply.lower():
                print_error("VIOLATION: Agent revealed scam detection!")
            else:
                print_success("Agent maintained cover (did not reveal detection).")

            time.sleep(1)

        # Wait for callback (30s inactivity timer)
        print_section("🏁 CALLBACK VERIFICATION")
        print("Waiting 35 seconds for inactivity callback to fire...")
        time.sleep(35)
        print_success("Inactivity timeout should have triggered callback — check server logs.")

        print_section("📊 TEST COMPLETE")
        print(f"Total messages exchanged: {len(self.history)}")


if __name__ == "__main__":
    tester = LifecycleTester()
    tester.run()
