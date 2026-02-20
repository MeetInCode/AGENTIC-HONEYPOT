import os
import glob
import re

PROMPT_DIR = r"c:\Users\Asus\Desktop\GUVI\agentic_honeypot\prompts"

FAKE_JSON = """{{
  "sessionId": "{session_id}",
  "scamDetected": true,
  "totalMessagesExchanged": 14,
  "engagementDurationSeconds": 210,
  "extractedIntelligence": {{
    "phoneNumbers": [
      "+91-9876543210",
      "+91-8765432109"
    ],
    "bankAccounts": [
      "1234567890123456",
      "6543210098765432"
    ],
    "upiIds": [
      "scammer.fraud@fakebank",
      "cashback.scam@fakeupi"
    ],
    "phishingLinks": [
      "http://malicious-site.com",
      "http://amaz0n-deals.fake-site.com/claim?id=12345",
      "http://fake-bank-kyc.com"
    ],
    "emailAddresses": [
      "scammer@fake.com",
      "offers@fake-amazon-deals.com"
    ],
    "caseIds": [
      "CASE-REF-00921",
      "TKT-FAKE-4471"
    ],
    "policyNumbers": [
      "POLICY-ULIP-778899",
      "INS-FRAUD-554433"
    ],
    "orderNumbers": [
      "ORDER-FAKE-2026-00123",
      "AMZ-DEL-99887766"
    ]
  }},
  "agentNotes": "Scammer claimed to be from SBI fraud department, shared fake case ID, policy and order details, and repeatedly pushed a KYC verification link and cashback UPI handle.",
  "scamType": "bank_fraud_upi_phishing_combo",
  "confidenceLevel": 0.96
}}"""

# Update judge agent
judge_path = os.path.join(PROMPT_DIR, "judge_agent.md")
with open(judge_path, 'r', encoding='utf-8') as f:
    judge_content = f.read()

# Replace everything from `{{` to `}}` before CRITICAL RULE
pattern = re.compile(r'\{\{\s*"sessionId":[\s\S]*?\}\}', re.MULTILINE)
new_judge_content = pattern.sub(FAKE_JSON, judge_content)

with open(judge_path, 'w', encoding='utf-8') as f:
    f.write(new_judge_content)
    
print("Updated judge_agent.md")

# We can also update the council prompts, though they don't produce the final payload.
# They produce AgentOutput, which does include scamType and confidence. But their fields differ a bit.
# Let's read council_scout to see if we should update it.
