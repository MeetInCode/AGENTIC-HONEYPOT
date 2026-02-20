import os
import glob
import re

PROMPT_DIR = r"c:\Users\Asus\Desktop\GUVI\agentic_honeypot\prompts"

EXACT_RULES = """- **Phone Numbers**: Any phone numbers shared by scammer
- **Bank Accounts**: Any bank account numbers mentioned
- **UPI IDs**: Any UPI IDs provided
- **Phishing Links**: Any suspicious URLs shared
- **Email Addresses**: Any email addresses shared
- **Case IDs**: Any case/reference IDs mentioned
- **Policy Numbers**: Any policy numbers shared
- **Order Numbers**: Any order IDs mentioned"""

# Update council prompts
for path in glob.glob(os.path.join(PROMPT_DIR, "council_*.md")):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the entity extraction section block to replace it
    # it usually starts after "**CRITICAL: NEVER fabricate data..."
    # We will use regex to replace all bullet points up to "- **Suspicious Keywords"
    
    pattern = re.compile(r'- \*\*UPI IDs\*\*:.*?(?=- \*\*Suspicious Keywords\*\*:)', re.DOTALL)
    if pattern.search(content):
        new_content = pattern.sub(EXACT_RULES + "\n", content)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {os.path.basename(path)}")
        
# Update judge prompt
judge_path = os.path.join(PROMPT_DIR, "judge_agent.md")
with open(judge_path, 'r', encoding='utf-8') as f:
    judge_content = f.read()
    
# Replace judge rules
judge_pattern = re.compile(r'- \*\*bankAccounts\*\*:.*?(?=- \*\*suspiciousKeywords\*\*:)', re.DOTALL | re.IGNORECASE)
if judge_pattern.search(judge_content):
    new_judge_content = judge_pattern.sub(EXACT_RULES + "\n   ", judge_content)
    with open(judge_path, 'w', encoding='utf-8') as f:
        f.write(new_judge_content)
    print("Updated judge_agent.md")

