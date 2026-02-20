# Honeypot API

## Description
An AI-powered honeypot system designed to detect scam messages, engage scammers autonomously, and extract actionable intelligence. It implements a dual-path Split-Process Architecture: an immediate synchronous path that replies instantly (<2s latency) using a configured persona, and an asynchronous path that uses a multi-model Detection Council to analyze intent, vote on the scam classification, and extract intelligence without blocking the chat.

## Tech Stack
- **Language/Framework:** Python 3.10+, FastAPI
- **Key libraries:** Pydantic, HTTPX, Uvicorn, Python-dotenv
- **LLM/AI models used:** 
  - Groq models: `meta-llama/llama-4-scout-17b-16e-instruct`, `openai/gpt-oss-120b`, `llama-3.3-70b-versatile`
  - NVIDIA NIM models: `nvidia/llama-3.3-nemotron-super-49b-v1`, `minimaxai/minimax-m2.1`

## Setup Instructions
1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd agentic_honeypot
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables:
   Copy `.env.example` to `.env` and fill in your API keys (`API_SECRET_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY`).
4. Run the application:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   *(Note: For Railway Deployment, the platform will automatically use the `Procfile` to run the application on the provided `$PORT`.)*

## API Endpoint
- **URL**: `https://<your-deployed-url>/honeypot/message`
- **Method**: POST
- **Authentication**: `x-api-key` header

## Approach
- **How you detect scams:** We utilize a "Detection Council" of 5 concurrent LLM agents (powered by Groq and NVIDIA NIM), each specialized in different domains (safety, linguistics, bot patterns, scam strategy). The agents vote independently on whether a message is a scam. A final "Judge" agent (Llama 3.3 70B) aggregates the votes to reach a consensus, avoiding false positives by evaluating contextual legitimacy.
- **How you extract intelligence:** We use a hybrid intelligence extraction pipeline that combines high-speed Regex heuristics with precise LLM-based entity extraction (using Llama-4-Scout) to capture phone numbers, emails, phishing links, bank accounts, UPI IDs, case numbers, and order numbers mentioned by scammers.
- **How you maintain engagement:** We employ a "Confused Cooperator" persona ("Ramesh Kumar" by default) generated using Llama-3.3-70b. The system generates short (1-2 sentences), highly natural responses mixing English and Hindi seamlessly. The agent pretends to comply, faces "technical issues," or asks clarifying questions, tricking the scammer into revealing more details (UPI IDs, bank accounts) while safely stalling without giving away real credentials.
