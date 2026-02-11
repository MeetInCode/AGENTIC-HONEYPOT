
import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def list_models():
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        print("No API Key found")
        return

    url = "https://integrate.api.nvidia.com/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    print(f"Querying {url}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("\nAvailable Models:")
            for m in data['data']:
                print(f" - {m['id']}")
        else:
            print(f"Error: {response.status_code} {response.text}")

if __name__ == "__main__":
    asyncio.run(list_models())
