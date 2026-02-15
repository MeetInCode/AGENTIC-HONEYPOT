# 🍯 Agentic Honeypot for Scam Detection & Intelligence Extraction

An AI-powered honeypot system that detects scam messages, engages scammers autonomously using LLM-based agents, and extracts actionable intelligence.

## 📋 Overview

This system implements a single-endpoint API (`POST /honeypot/message`) that:
1.  **Instantly Relies**: Provides a synchronous, human-like response to the scammer.
2.  **Analyzes Asynchronously**: Uses a multi-model **Detection Council** to classify scams and extract intelligence in the background.
3.  **Reports to Core**: Sends a mandatory final callback with aggregated intelligence to the GUVI evaluation endpoint.

Built for the GUVI Hackathon challenge.

### Key Features

-   **Dual-Path Architecture**:
    -   **Sync Path**: Instant replies (<2s latency) using highly optimized LLMs.
    -   **Async Path**: Deep analysis, voting, and intelligence extraction without blocking the chat.
-   **5-Agent Detection Council**: A mix of NVIDIA NIM and Groq models for robust scam classification.
-   **Hybrid Intelligence Extraction**: Combines high-speed Regex with Llama-4-Scout for precise entity extraction (UPIs, Banks, Links).
-   **Persona-based Engagement**: "Ramesh Kumar" — a believable, confused victim persona that keeps scammers engaged.
-   **Judge Agent**: A final Llama 3.3 70B aggregator that compiles all findings into a strict JSON payload.

## 🏗️ Architecture

The system uses a **Split-Process Architecture** to ensure responsiveness while performing heavy analysis.

```mermaid
graph TD
    User[Evaluator/Scammer] -->|POST /honeypot/message| API[FastAPI Gateway]
    
    API -->|1. Immediate| ReplyGen[Response Generator]
    ReplyGen -->|2. Sync Reply| User
    
    API -.->|3. Background Task| Orchestrator
    
    subgraph "Async Intelligence Pipeline"
        Orchestrator --> Council[Detection Council (5 Agents)]
        Orchestrator --> Extractor[Intel Extractor (Regex + LLM)]
        
        Council -->|Votes| Judge[Judge Agent (Llama 3.3)]
        Extractor -->|Entities| Judge
        
        Judge -->|Final Decision| Callback[Callback Service]
    end
    
    Callback -->|POST Result| GUVI[GUVI Evaluation Endpoint]
```

## 🧪 Detection Council Members

The "Brain" of the honeypot runs **5 concurrent voters** by default (configurable via `.env`):

| Agent | Model Provider | Model | Specialty |
| :--- | :--- | :--- | :--- |
| **NemotronVoter** | NVIDIA | `nvidia/llama-3.3-nemotron-super-49b-v1` | **Shield & Safety**: Expert in identifying harmful or fraudulent content. |
| **MinimaxVoter** | NVIDIA | `minimaxai/minimax-m2.1` | **Linguistics**: Analyzes tone, urgency, and social engineering patterns. |
| **LlamaScoutVoter** | Groq | `meta-llama/llama-4-scout-17b-16e-instruct` | **Realism & Anomalies**: Spots bot-like templates vs human scammers. (Runs 2 instances by default) |
| **GptOssVoter** | Groq | `openai/gpt-oss-120b` | **Scam Strategy**: Identifies specific playbooks (Digital Arrest, Job Scam, etc.). |

> **Note**: `GroqCompoundVoter` and `QwenVoter` are also available but disabled by default (set `COUNCIL_COMPOUND_COUNT=1` or `COUNCIL_QWEN_COUNT=1` to enable).

## 🚀 Quick Start

### Prerequisites

-   Python 3.10+
-   Groq API Key
-   NVIDIA NIM API Key

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd agentic_honeypot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Copy the example environment file and add your keys:

```bash
cp .env.example .env
```

```ini
# API Security
API_SECRET_KEY=your_secret_key_here

# LLM API Keys
GROQ_API_KEY=gsk_...
NVIDIA_API_KEY=nvapi-...

# Optional: Dedicated Agent Keys
COUNCIL_LLAMA_SCOUT_API_KEY=...
COUNCIL_GPT_OSS_API_KEY=...
COUNCIL_NEMOTRON_API_KEY=...
COUNCIL_MINIMAX_API_KEY=...

# Council Configuration (Number of Voters)
COUNCIL_SCOUT_COUNT=2
COUNCIL_GPT_OSS_COUNT=1
COUNCIL_NEMOTRON_COUNT=1
COUNCIL_MINIMAX_COUNT=1
COUNCIL_COMPOUND_COUNT=0
COUNCIL_QWEN_COUNT=0

# Application Settings
INACTIVITY_TIMEOUT_SECONDS=20
MAX_CONVERSATION_TURNS=20
SCAM_CONFIDENCE_THRESHOLD=0.6
COUNCIL_DELAY_SECONDS=3.0

# Server Configuration
PORT=8000
WORKERS=4                # Number of background worker tasks
DEBUG=false
LOG_LEVEL=INFO

# Request Limits
MAX_MESSAGE_LENGTH=10000
REQUEST_TIMEOUT=30.0
```

### Running the Server

**Development Mode:**
```bash
# Start with auto-reload (single worker)
python main.py
# Or set DEBUG=true in .env
```

**Production Mode:**
```bash
# Set DEBUG=false and WORKERS=4+ in .env
python main.py

# Or use gunicorn/uvicorn directly:
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Concurrent Request Handling:**
- FastAPI handles concurrent requests natively using async/await
- Multiple worker processes (set via `WORKERS` env var) enable true parallelism
- Each worker can handle thousands of concurrent connections
- Background tasks (intel pipeline) run independently without blocking responses
- API key rotation pool automatically distributes load across multiple keys

## 📖 API Documentation

### Main Endpoint

**POST** `/honeypot/message`

**Headers:**
-   `x-api-key`: Your configured secret key
-   `Content-Type`: `application/json`

**Request Body:**
```json
{
  "sessionId": "unique-session-id",
  "message": {
    "sender": "scammer",
    "text": "Your SBI account is blocked. Click here: http://bit.ly/fake",
    "timestamp": 1700000000
  },
  "conversationHistory": []
}
```

**Response (Immediate):**
```json
{
  "sessionId": "unique-session-id",
  "status": "success",
  "reply": "Oh no! Why is it blocked? I am scared.",
  "scamDetected": true,
  "confidence": 0.95
}
```

### Mandatory Callback

The system autonomously sends the final analysis to the configured GUVI endpoint when:
1.  Specific high-confidence intelligence (UPI, Link) is found.
2.  Or 15 seconds have passed (Hard Deadline).
3.  Or the conversation goes inactive.

**Callback Payload:**
```json
{
  "sessionId": "unique-session-id",
  "scamDetected": true,
  "totalMessagesExchanged": 5,
  "extractedIntelligence": {
    "bankAccounts": [],
    "upiIds": ["scammer@ybl"],
    "phishingLinks": ["http://bit.ly/fake"],
    "phoneNumbers": [],
    "suspiciousKeywords": ["blocked", "SBI", "click here"]
  },
  "agentNotes": "Bank fraud scam detected. Scammer attempted to harvest credentials via phishing link."
}
```

## 📂 Project Structure

```
agentic_honeypot/
├── main.py                 # FastAPI Entry Point
├── core/
│   └── orchestrator.py     # Logic Coordinator (Sync vs Async paths)
├── agents/                 # AI Agents
│   ├── detection_council.py # Parallel Voter Runner
│   ├── nvidia_agents.py    # Nemotron, Minimax Agents
│   ├── groq_agents.py      # LlamaScout, GPT-OSS Agents
│   └── meta_moderator.py   # Judge Agent (Aggregator)
├── engagement/
│   ├── response_generator.py # "Ramesh Kumar" Persona Logic
│   └── persona_manager.py    # System Prompts & Context
├── services/
│   ├── intelligence_extractor.py # Regex + LLM Extraction
│   ├── session_manager.py    # In-Memory State
│   └── callback_service.py   # GUVI Callback Handler
├── models/
│   └── schemas.py          # Pydantic Models
└── config/
    └── settings.py         # Configuration Management
```

## 🛠️ Tech Stack

-   **Framework**: FastAPI
-   **Runtime**: Python 3.10+ (Asyncio)
-   **LLM Providers**:
    -   **Groq**: Ultra-low latency inference for engagement & scouting.
    -   **NVIDIA NIM**: Specialized safety and linguistics models.
-   **Validation**: Pydantic
-   **Network**: HTTPX

## 📄 License

MIT License - Built for GUVI Hackathon 2024
