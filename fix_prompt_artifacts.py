import os
import glob
import re

PROMPT_DIR = r"c:\Users\Asus\Desktop\GUVI\agentic_honeypot\prompts"

# Fix council files
for path in glob.glob(os.path.join(PROMPT_DIR, "council_*.md")):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove the trailing artifact
    bad_string = "found.,\n  \"notes\": \"Concise 2-3 line summary of the scammer's specific technique, scripted patterns, and anomalies detected.\"\n}}"
    if bad_string in content:
        content = content.replace(bad_string, "found.")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {os.path.basename(path)}")

# Fix judge_agent.md
judge_path = os.path.join(PROMPT_DIR, "judge_agent.md")
with open(judge_path, 'r', encoding='utf-8') as f:
    judge_content = f.read()

bad_judge = "empty array.,\n  \"agentNotes\": \"Payment fraud detected. Scammer used urgency tactics requesting UPI transfer. Extracted UPI ID and suspicious keywords.\"\n}}"
if bad_judge in judge_content:
    judge_content = judge_content.replace(bad_judge, "empty array.")
    with open(judge_path, 'w', encoding='utf-8') as f:
        f.write(judge_content)
    print("Fixed judge_agent.md")

