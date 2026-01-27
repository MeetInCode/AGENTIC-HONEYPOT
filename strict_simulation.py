import requests
import json
import time
import uuid
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
ENDPOINT_URL = "https://web-production-f5c68.up.railway.app/api/v1/analyze"  # Ensure this matches your deployment
API_KEY = "hp_live_9fA3kLQxP2Z8R7sM1"     # Ensure this matches your deployment

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    AGENT = '\033[92m'   # Added alias for clarity
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_section(title):
    print(f"\n{Colors.HEADER}{'='*60}\n{title.center(60)}\n{'='*60}{Colors.ENDC}")

def validate_response_schema(data):
    """
    Validates the API response against the schema in Section 8.
    """
    required_keys = [
        "status", 
        "scamDetected", 
        "engagementMetrics", 
        "extractedIntelligence", 
        "agentNotes"
    ]
    
    missing = [k for k in required_keys if k not in data]
    
    if missing:
        print(f"{Colors.FAIL}❌ Schema Validation Failed! Missing keys: {missing}{Colors.ENDC}")
        return False
    
    # Validate nested objects
    if not isinstance(data.get("engagementMetrics"), dict):
        print(f"{Colors.FAIL}❌ Schema Validation Failed! 'engagementMetrics' should be a dict.{Colors.ENDC}")
        return False

    if not isinstance(data.get("extractedIntelligence"), dict):
        print(f"{Colors.FAIL}❌ Schema Validation Failed! 'extractedIntelligence' should be a dict.{Colors.ENDC}")
        return False

    print(f"{Colors.OKGREEN}✅ Response Schema Validated{Colors.ENDC}")
    return True

def run_simulation():
    session_id = str(uuid.uuid4())
    print_section(f"🕵️ STRICT COMPLIANCE SIMULATION\nSession ID: {session_id}")
    
    history = []
    
    # ==================================================================================
    # STEP 1: First Message (Section 6.1)
    # ==================================================================================
    print(f"\n{Colors.BOLD}--- Step 1: Sending Initial Scam Message (Section 6.1) ---{Colors.ENDC}")
    
    first_msg_text = "Your bank account will be blocked today. Verify immediately."
    timestamp1 = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    payload_1 = {
        "sessionId": session_id,
        "message": {
            "sender": "scammer",
            "text": first_msg_text,
            "timestamp": timestamp1
        },
        "conversationHistory": [], # Empty for first message
        "metadata": {
            "channel": "SMS",
            "language": "English",
            "locale": "IN"
        }
    }
    
    print(f"{Colors.OKBLUE}Request 1 Payload:{Colors.ENDC}")
    print(json.dumps(payload_1, indent=2))
    
    try:
        response_1 = requests.post(ENDPOINT_URL, headers={"x-api-key": API_KEY, "Content-Type": "application/json"}, json=payload_1)
        response_1.raise_for_status()
        data_1 = response_1.json()
        
        print(f"{Colors.OKCYAN}Response 1:{Colors.ENDC}")
        print(json.dumps(data_1, indent=2))
        
        validate_response_schema(data_1)
        
        # Prepare history for next step
        history.append(payload_1["message"])
        
        # We need the AGENT'S reply to put into the history for the next turn
        # The problem statement example 6.2 assumes the user replied.
        # Your API might return 'agentResponse' in the root or 'message' object depending on implementation.
        # Based on previous file, it seems the User's API returns 'agentResponse' at root? 
        # Wait, Section 8 'Expected Output Format' DOES NOT showing 'agentResponse' or 'message' field!
        # This is a discrepancy in the problem statement?
        # Section 8 shows: status, scamDetected, engagementMetrics, extractedIntelligence, agentNotes.
        # IT DOES NOT SHOW THE AGENT'S REPLY MESSAGE TEXT.
        # However, Section 3 says "Engages scammers autonomously".
        # If the API doesn't return the text, how does the scammer know what to say?
        # usually it is in a field.
        # Let's check the users 'simulate_honeypot.py' again. It specifically looks for `response_data.get("agentResponse")`.
        # I will assume the API returns 'agentResponse' (or similar) even if Section 8 missed it, 
        # or it's wrapped inside execution. 
        # I will check for 'agentResponse' dynamically.
        
        agent_reply = data_1.get("agentResponse") or data_1.get("message", {}).get("text") or "Hello?"
        
        print(f"{Colors.AGENT}Agent Reply used for history: {agent_reply}{Colors.ENDC}")
        
        agent_msg_obj = {
            "sender": "user",
            "text": agent_reply,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        history.append(agent_msg_obj)
        
    except Exception as e:
        print(f"{Colors.FAIL}Step 1 Failed: {e}{Colors.ENDC}")
        return

    # ==================================================================================
    # STEP 2: Second Message (Section 6.2)
    # ==================================================================================
    print(f"\n{Colors.BOLD}--- Step 2: Sending Follow-Up Scam Message (Section 6.2) ---{Colors.ENDC}")
    
    second_msg_text = "Share your UPI ID to avoid account suspension."
    timestamp2 = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    payload_2 = {
        "sessionId": session_id,
        "message": {
            "sender": "scammer",
            "text": second_msg_text,
            "timestamp": timestamp2
        },
        "conversationHistory": history, # Now populated
        "metadata": {
            "channel": "SMS",
            "language": "English",
            "locale": "IN"
        }
    }
    
    print(f"{Colors.OKBLUE}Request 2 Payload:{Colors.ENDC}")
    print(json.dumps(payload_2, indent=2))
    
    try:
        response_2 = requests.post(ENDPOINT_URL, headers={"x-api-key": API_KEY, "Content-Type": "application/json"}, json=payload_2)
        response_2.raise_for_status()
        data_2 = response_2.json()
        
        print(f"{Colors.OKCYAN}Response 2:{Colors.ENDC}")
        print(json.dumps(data_2, indent=2))
        
        validate_response_schema(data_2)
        
        if data_2.get("scamDetected"):
            print(f"{Colors.OKGREEN}✅ Scam successfully detected!{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}⚠️ Scam NOT yet detected.{Colors.ENDC}")
            
    except Exception as e:
        print(f"{Colors.FAIL}Step 2 Failed: {e}{Colors.ENDC}")
        return

    print_section("🏁 EXPECTED SIMULATION COMPLETE")
    print("If you need to test the MANDATORY CALLBACK, reliable full-flow simulation with 5-10 turns is recommended.")

if __name__ == "__main__":
    run_simulation()
