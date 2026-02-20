import os
import glob
import re

PROMPT_DIR = r"c:\Users\Asus\Desktop\GUVI\agentic_honeypot\prompts"
council_files = glob.glob(os.path.join(PROMPT_DIR, "council_*.md"))

NEW_COUNCIL_JSON = """{{
  "scamDetected": true,
  "confidence": 0.88,
  "scamType": "template_scam",
  "extractedIntelligence": {{
    "upiIds": ["primary@paytm"],
    "suspiciousKeywords": ["immediately", "urgent", "verify now"]
  }},
  "notes": "Concise 2-3 line summary of the scammer's specific technique, scripted patterns, and anomalies detected."
}}

**CRITICAL RULE FOR INTELLIGENCE:** ONLY include keys in `extractedIntelligence` if they contain values. DO NOT send empty arrays like `"bankAccounts": []` or `"phishingLinks": []`. Omit the key entirely if the intelligence is not found.
"""

# Generic replacement for council notes
# They might have different notes like "Concise 2-3 line summary..."
def update_council_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We locate the entire OUTPUT FORMAT block
    # Start: "Return ONLY valid JSON"
    # End: "}}""
    
    # Regex to replace everything from {{ to }} under OUTPUT FORMAT
    pattern = re.compile(r'\{\{\s*"scamDetected":[\s\S]*?\}\}', re.MULTILINE)
    
    # Also add the critical rule text after it
    if "CRITICAL RULE FOR INTELLIGENCE:" not in content:
        new_content = pattern.sub(NEW_COUNCIL_JSON.strip(), content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {os.path.basename(file_path)}")

for f in council_files:
    update_council_json(f)

# Update judge_agent.md
judge_path = os.path.join(PROMPT_DIR, "judge_agent.md")
with open(judge_path, 'r', encoding='utf-8') as f:
    judge_content = f.read()

# Make the judge prompt omit empty arrays
JUDGE_JSON = """{{
  "sessionId": "{session_id}",
  "scamDetected": true,
  "confidence": 0.85,
  "scamType": "payment_fraud",
  "totalMessagesExchanged": {total_msg_count},
  "engagementDurationSeconds": 120.0,
  "extractedIntelligence": {{
    "upiIds": ["example@ybl"],
    "suspiciousKeywords": ["urgent", "verify"]
  }},
  "agentNotes": "Payment fraud detected. Scammer used urgency tactics requesting UPI transfer. Extracted UPI ID and suspicious keywords."
}}

**CRITICAL RULE FOR INTELLIGENCE:** ONLY include keys in `extractedIntelligence` if they contain values. DO NOT include empty arrays like `"bankAccounts": []` or `"phishingLinks": []`. If no keywords are found, omit `"suspiciousKeywords"` entirely instead of sending an empty array.
"""

# Replace in judge agent
pattern = re.compile(r'\{\{\s*"sessionId":[\s\S]*?\}\}', re.MULTILINE)
if "CRITICAL RULE FOR INTELLIGENCE:" not in judge_content:
    new_judge = pattern.sub(JUDGE_JSON.strip(), judge_content)
    with open(judge_path, 'w', encoding='utf-8') as f:
        f.write(new_judge)
    print("Updated judge_agent.md")

