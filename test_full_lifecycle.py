import requests
import json
import time
import uuid
from datetime import datetime, timezone
import sys

# Configuration
BASE_URL = "https://0c6411b68eaa.ngrok-free.app/api/honeypot"
API_KEY = "test-key-123"

# Colors for terminal output
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

def print_json(data):
    print(json.dumps(data, indent=2))

class LifecycleTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.history = []
        self.headers = {
            "x-api-key": API_KEY,
            "Content-Type": "application/json"
        }
        
    def send_message(self, text, sender="scammer"):
        url = f"{BASE_URL}"
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
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print_error(f"Request failed: {e}")
            return None

    def get_session_status(self):
        try:
            url = f"{BASE_URL}/api/v1/session/{self.session_id}"
            response = requests.get(url, headers=self.headers)
            return response.json()
        except:
            return {}

    def run(self):
        print_section("🕵️  AGENTIC HONEYPOT FULL LIFECYCLE TEST")
        print(f"Session ID: {self.session_id}")
        
        # --- SCENARIO: Bank Fraud ---
        conversation_flow = [
            "Dear customer, your HDFC bank account will be blocked today due to pending KYC. Click link: http://hdfc-kyc-update.com",
            # Agent should respond asking what to do
            "Yes this is Manager. Please share your Aadhar number and OTP to stop blocking.",
            # Agent should potentially fake an OTP or ask more questions
            "Don't delay. Also transfer Rs 10 to verify UPI ID: scammer@upi. This is refundable.",
            # Agent should capture this UPI
            "Why are you not replying? Police will come to your house if you don't verify."
        ]
        
        for i, msg in enumerate(conversation_flow):
            print_step(i + 1, f"Scammer says: \"{msg}\"")
            
            # Send Request
            data = self.send_message(msg)
            if not data:
                break
                
            # validations
            is_scam = data.get("scamDetected")
            agent_response = data.get("agentResponse")
            intel = data.get("extractedIntelligence", {})
            metrics = data.get("engagementMetrics", {})
            
            # Update History
            self.history.append({"sender": "scammer", "text": msg, "timestamp": datetime.now(timezone.utc).isoformat()})
            if agent_response:
                self.history.append({"sender": "user", "text": agent_response, "timestamp": datetime.now(timezone.utc).isoformat()})
            
            # --- DETAILED OUTPUT ---
            print(f"{Colors.CYAN}--- API Response Analysis ---{Colors.ENDC}")
            print(f"🛡️  Scam Detected: {is_scam}")
            print(f"🤖 Agent Response: {Colors.WARNING}\"{agent_response}\"{Colors.ENDC}")
            print(f"📝 Agent Notes: {data.get('agentNotes', 'N/A')}")
            
            if "extractedIntelligence" in data:
                print(f"🧠 Extracted Intel: {json.dumps(data['extractedIntelligence'], indent=2)}")
            
            if "engagementMetrics" in data:
                print(f"⏱️  Duration: {metrics.get('engagementDurationSeconds')}s | Loops: {metrics.get('totalMessagesExchanged')}")

            # Verification of Constraints
            if i == 0 and is_scam:
                print_success("Scam correctly detected on first turn.")
            
            if agent_response and "scam" in agent_response.lower() and "detected" in agent_response.lower():
                 print_error("VIOLATION: Agent revealed scam detection!")
            else:
                 print_success("Agent maintained cover (did not reveal detection).")

            time.sleep(1) 

        # --- FINAL STAGE: Callback Verification ---
        print_section("🏁 FINAL CALLBACK VERIFICATION")
        print("Checking session status on server (waiting for background task)...")
        
        # Wait loop for callback
        for i in range(10):
            session_data = self.get_session_status()
            if session_data.get("callback_sent"):
                break
            time.sleep(1)
        
        print_json(session_data)
        
        if session_data.get("callback_sent"):
            print_success("Callback to GUVI Endpoint was triggered.")
            print(f"{Colors.GREEN}📄 Callback Response Log: {session_data.get('callback_response_log')}{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}⚠️  Callback not confirmed yet. It might still be processing.{Colors.ENDC}")
            if session_data.get("callback_response_log"):
                 print(f"📄 Response Log: {session_data.get('callback_response_log')}")

        # Summary of Intel
        print_section("📊 INTEL ACCUMULATED")
        # Just getting the intel from the last packet or session
        print_json(session_data.get("extracted_intelligence", {}))

if __name__ == "__main__":
    tester = LifecycleTester()
    tester.run()
