import os
import glob
import re

PROMPT_DIR = r"c:\Users\Asus\Desktop\GUVI\agentic_honeypot\prompts"
council_files = glob.glob(os.path.join(PROMPT_DIR, "council_*.md"))

ADDITIONAL_RULES = """- **Bank Accounts**: Actual account numbers (digits only, e.g. "1234567890"). Not masked like "XXXXXXX1234" or descriptions.
- **Email Addresses**: Any email addresses mentioned.
- **Case IDs**: Any case or reference IDs mentioned.
- **Policy Numbers**: Any policy numbers mentioned.
- **Order Numbers**: Any order IDs or transaction numbers mentioned."""

for path in council_files:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the bank accounts line to include all the new rules
    if "Case IDs" not in content:
        # Some prompts might have "Bank Accounts" in ENTITY EXTRACTION
        content = re.sub(
            r'- \*\*Bank Accounts\*\*: Actual account numbers.*?descriptions\.',
            ADDITIONAL_RULES,
            content,
            flags=re.DOTALL
        )
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {os.path.basename(path)}")

# Update judge_agent
judge_path = os.path.join(PROMPT_DIR, "judge_agent.md")
with open(judge_path, 'r', encoding='utf-8') as f:
    judge_content = f.read()

# Make sure judge agent explicitly emphasizes them
if "CRITICAL: You MUST extract Case IDs, Policy Numbers, and Order Numbers" not in judge_content:
    judge_content = judge_content.replace(
        "5. **extractedIntelligence**: Merge from all agents with STRICT rules:",
        "5. **extractedIntelligence**: Merge from all agents with STRICT rules. CRITICAL: You MUST extract Case IDs, Policy Numbers, and Order Numbers if they appear in the conversation."
    )
    with open(judge_path, 'w', encoding='utf-8') as f:
        f.write(judge_content)
    print("Updated judge_agent.md")

