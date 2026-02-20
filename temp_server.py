import uvicorn
from fastapi import FastAPI, Request
import json
import logging

# Mute uvicorn access logs for clean output
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI()

@app.post("/callback")
async def receive_callback(request: Request):
    try:
        data = await request.json()
        print("\n" + "🌟"*40)
        print("🔔 CALLBACK RECEIVED AT TEMP SERVER:")
        print(json.dumps(data, indent=2))
        print("🌟"*40 + "\n")
        return {"status": "success", "message": "Callback received"}
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return {"status": "error"}

if __name__ == "__main__":
    print("Temp callback server running on port 8111...")
    uvicorn.run(app, host="127.0.0.1", port=8111, log_level="warning")
