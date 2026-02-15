import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_prompt_loading():
    print("Checking prompt loading...")
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(root_dir, "prompts")
    
    print(f"Project root: {root_dir}")
    print(f"Prompts dir: {prompts_dir}")
    
    expected_files = [
        "reply_agent.md",
        "judge_agent.md",
        "council_minimax.md",
        "council_nemotron.md",
        "council_gpt_oss.md",
        "council_prompt_guard.md",
        "council_scout.md",
        "council_contextual.md"
    ]
    
    all_exist = True
    for f in expected_files:
        path = os.path.join(prompts_dir, f)
        if os.path.exists(path):
            print(f"[OK] Found {f}")
        else:
            print(f"[FAIL] Missing {f} at {path}")
            all_exist = False
            
    if all_exist:
        print("\nAll prompt files found.")
    else:
        print("\nSome prompt files are missing.")

    print("\nAttempting to import agent modules to check for syntax/import errors...")
    try:
        from agents.groq_agents import GroqVoter
        print("[OK] Imported agents.groq_agents")
    except Exception as e:
        print(f"[FAIL] Failed to import agents.groq_agents: {e}")

    try:
        from agents.nvidia_agents import NvidiaVoter
        print("[OK] Imported agents.nvidia_agents")
    except Exception as e:
        print(f"[FAIL] Failed to import agents.nvidia_agents: {e}")

    try:
        from agents.meta_moderator import JudgeAgent
        print("[OK] Imported agents.meta_moderator")
    except Exception as e:
        print(f"[FAIL] Failed to import agents.meta_moderator: {e}")
        
    try:
        from engagement.response_generator import ResponseGenerator
        print("[OK] Imported engagement.response_generator")
    except Exception as e:
        print(f"[FAIL] Failed to import engagement.response_generator: {e}")

if __name__ == "__main__":
    check_prompt_loading()
