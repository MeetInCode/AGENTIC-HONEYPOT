import requests
import json
import time
import uuid
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env for GROQ_API_KEY
load_dotenv()

# ==========================================
# ⚙️ CONFIGURATION (Change these)
# ==========================================
# Use ngrok if provided, or set your ngrok URL here
ENDPOINT_URL = "https://web-production-f5c68.up.railway.app/api/v1/analyze" 
API_KEY = "hp_live_9fA3kLQxP2Z8R7sM1"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# ==========================================

class Colors:
    HEADER = '\033[95m'
    SCAMMER = '\033[91m' # Red
    AGENT = '\033[92m'   # Green
    INFO = '\033[94m'    # Blue
    CYAN = '\033[96m'
    WARNING = '\033[93m'
    GREEN = '\033[92m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_banner(text):
    print(f"\n{Colors.HEADER}{'='*70}\n{text.center(70)}\n{'='*70}{Colors.ENDC}")

class HoneypotSimulation:
    def __init__(self, endpoint, api_key, groq_key):
        self.endpoint = endpoint
        self.api_key = api_key
        self.groq_key = groq_key
        self.session_id = str(uuid.uuid4())
        self.history = []
        self.turns = 0

    def get_scammer_message(self, last_agent_message=None):
        """Uses Groq to act as a professional scammer."""
        if not self.groq_key:
            return "Urgent: Your bank account is blocked. Verification needed."
            
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.groq_key}"}
        
        system_prompt = (
            "You are a sophisticated professional scammer. Your goal is to extract "
            "KYC details, Aadhar numbers, OTPs, or get the victim to click a phishing link. "
            "Be persistent but sound 'official' or 'helpful'. Do not reveal you are an AI. "
            "Stay in character. Keep responses short (under 25 words)."
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add context of the current conversation
        for h in self.history:
            role = "user" if h["sender"] == "scammer" else "assistant"
            messages.append({"role": role, "content": h["text"]})
            
        if last_agent_message:
            messages.append({"role": "assistant", "content": last_agent_message})
        else:
            messages.append({"role": "user", "content": "Start the scam conversation."})

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 100
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers)
            return resp.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f"SCAM: Verify your account now at http://bit.ly/secure-kyc-{uuid.uuid4().hex[:4]}"

    def send_to_honeypot(self, text):
        """Sends the scammer's message to the Honeypot API."""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "sessionId": self.session_id,
            "message": {
                "sender": "scammer",
                "text": text,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            },
            "conversationHistory": self.history,
            "metadata": {"channel": "WhatsApp", "language": "English", "locale": "IN"}
        }
        
        start_time = time.time()
        print(f"\n{Colors.INFO}[OUTGOING TO API]{Colors.ENDC}")
        print(f"URL: {self.endpoint}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(self.endpoint, json=payload, headers=headers)
        latency = time.time() - start_time
        
        try:
            return response.json(), latency
        except json.JSONDecodeError:
            print(f"\n{Colors.WARNING}❌ Failed to decode JSON response from API.{Colors.ENDC}")
            print(f"Status Code: {response.status_code}")
            print(f"Raw Response: {response.text}")
            raise

    def check_callback_status(self):
        """Checks if the server-side callback was triggered."""
        # Note: We use the session endpoint we created earlier
        status_url = self.endpoint.replace("/analyze", f"/session/{self.session_id}")
        headers = {"x-api-key": self.api_key}
        
        try:
            resp = requests.get(status_url, headers=headers)
            return resp.json()
        except:
            return None

    def run(self, max_turns=4):
        print_banner(f"🚀 STARTING SCAM SIMULATION (Session: {self.session_id})")
        print(f"{Colors.BOLD}Target Endpoint:{Colors.ENDC} {self.endpoint}")
        
        last_agent_msg = None
        
        for turn in range(max_turns):
            self.turns += 1
            print(f"\n{Colors.CYAN}{'='*30} TURN {turn+1} {'='*30}{Colors.ENDC}")
            
            # 1. Scammer (Groq) generates message
            scammer_text = self.get_scammer_message(last_agent_msg)
            print(f"{Colors.SCAMMER}{Colors.BOLD}😈 Scammer:{Colors.ENDC} {scammer_text}")
            
            # 2. Send to Honeypot API
            response_data, latency = self.send_to_honeypot(scammer_text)
            
            # 3. Process Response
            print(f"\n{Colors.INFO}[INCOMING FROM API] (Latency: {latency:.2f}s){Colors.ENDC}")
            print(json.dumps(response_data, indent=2))
            
            agent_reply = response_data.get("agentResponse")
            scam_detected = response_data.get("scamDetected", False)
            
            if scam_detected:
                print(f"\n{Colors.AGENT}✨ API DETECTED SCAM! Agent Activated.{Colors.ENDC}")
            
            if agent_reply:
                print(f"{Colors.AGENT}{Colors.BOLD}🤖 Honeypot Agent:{Colors.ENDC} {agent_reply}")
                last_agent_msg = agent_reply
            else:
                print(f"{Colors.INFO}ℹ️ No agent response yet (listening phase).{Colors.ENDC}")
            
            # Update History
            self.history.append({"sender": "scammer", "text": scammer_text})
            if agent_reply:
                self.history.append({"sender": "user", "text": agent_reply})
                
            time.sleep(1)

        # 4. Final Verification
        print_banner("🏁 SIMULATION COMPLETE - VERIFYING CALLBACK")
        
        status = self.check_callback_status()
        if status:
            print(f"{Colors.CYAN}--- Final Server State ---{Colors.ENDC}")
            print(json.dumps(status, indent=2))
            
            if status.get("callback_sent"):
                print_banner("✅ MANDATORY CALLBACK SUCCESSFUL")
                print(f"{Colors.GREEN}Server confirmed it sent the intelligence to GUVI.{Colors.ENDC}")
                print(f"Response Log: {status.get('callback_response_log')}")
            else:
                print(f"{Colors.WARNING}⚠️ Callback not sent yet. (Intelligence might be insufficient or session still open).{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}❌ Could not fetch session status.{Colors.ENDC}")

if __name__ == "__main__":
    # If user wants to pass args via terminal in future, they can. For now, using config above.
    sim = HoneypotSimulation(ENDPOINT_URL, API_KEY, GROQ_API_KEY)
    sim.run()
