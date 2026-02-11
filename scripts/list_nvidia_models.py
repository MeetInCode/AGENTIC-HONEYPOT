
import asyncio
import httpx
import sys
import os

# Add parent dir to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from config.settings import get_settings

async def main():
    settings = get_settings()
    api_key = settings.nvidia_api_key
    base_url = "https://integrate.api.nvidia.com/v1" # Hardcoded to match standard
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    print(f"Checking {base_url}/models ...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/models", headers=headers)
        if response.status_code == 200:
            models = response.json().get("data", [])
            print(f"Found {len(models)} models.")
            
            # Filter for relevant models
            relevant = [
                m['id'] for m in models 
                if any(k in m['id'].lower() for k in ['nemotron', 'deepseek', 'minimax', 'llama-3.1-70b'])
            ]
            
            print("\nRelevant Models:")
            for m in relevant:
                print(m)
        else:
            print(f"Error: {response.status_code} {response.text}")

if __name__ == "__main__":
    asyncio.run(main())
