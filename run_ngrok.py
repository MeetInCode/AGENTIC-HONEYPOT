"""
Script to expose the local server via ngrok and display connection details.
"""
import os
import sys
import time
from pyngrok import ngrok, conf
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def expose_and_print():
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("API_SECRET_KEY")
    if not api_key:
        print("❌ Error: API_SECRET_KEY not found in .env")
        return

    print("\n🚀 Starting ngrok tunnel...")
    
    try:
        # Check if auth token is needed/present (optional but recommended)
        # For now, we try to connect anonymously or with whatever system config exists
        
        # Open a HTTP tunnel on standard port 8000
        # return_ngrok_tunnel=True returns the object
        public_url = ngrok.connect(8000).public_url
        
        print("\n" + "="*50)
        print("🌍 HONEYPOT PUBLIC ENDPOINT DETAILS")
        print("="*50)
        print(f"\nUse these details for the Honeypot API Endpoint Tester:\n")
        
        print(f"🔗 Honeypot API Endpoint URL:")
        print(f"   {public_url}/api/v1/analyze")
        print(f"   (Base URL: {public_url})")
        
        print(f"\n🔑 x-api-key:")
        print(f"   {api_key}")
        
        print("\n" + "="*50)
        print("Press Ctrl+C to stop the tunnel...")
        
        # Keep the script running to keep the tunnel open
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("🛑 Stopping ngrok tunnel...")
            ngrok.kill()
            
    except Exception as e:
        print(f"\n❌ Error starting ngrok: {e}")
        print("Note: You may need to sign up at ngrok.com and run `ngrok config add-authtoken <token>` if you haven't.")

if __name__ == "__main__":
    expose_and_print()
