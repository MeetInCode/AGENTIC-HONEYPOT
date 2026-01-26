# 🍯 Agentic Honeypot for Scam Detection & Intelligence Extraction

An AI-powered honeypot system that detects scam messages, engages scammers autonomously using LLM-based agents, and extracts actionable intelligence.

## 📋 Overview

This system implements a multi-model **Detection Council** for scam classification and a **LangGraph-based Engagement Agent** for autonomous scammer interaction. Built for the GUVI Hackathon challenge.

### Key Features

- **Multi-Model Detection Council**: 7 specialized agents for robust scam detection
- **LangGraph Engagement**: Stateful, multi-turn conversation management
- **Intelligence Extraction**: Automated extraction of UPI IDs, phone numbers, phishing links
- **Persona-based Engagement**: Believable victim personas for realistic interaction
- **Mandatory Callback**: Automatic result submission to GUVI evaluation endpoint

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Gateway                          │
│                   (API Key Authentication)                   │
└─────────────────────────┬─────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────┐
│                  Honeypot Orchestrator                        │
└─────────┬───────────────┬────────────────────┬───────────────┘
          │               │                    │
┌─────────▼────────┐ ┌────▼────────────┐ ┌─────▼──────────────┐
│Detection Council │ │ Engagement      │ │ Intelligence       │
│                  │ │ Graph           │ │ Extractor          │
│ 🕵️ RuleGuard    │ │ (LangGraph)     │ │                    │
│ 🧮 FastML       │ │                 │ │ • Regex            │
│ 🤖 BertLite     │ │ • Persona Mgr   │ │ • NER (spaCy)      │
│ 📜 LexJudge     │ │ • Response Gen  │ │ • LLM Extraction   │
│ 🔍 Sentinel     │ │ • State Graph   │ │                    │
│ 🧵 ContextSeer  │ │                 │ │                    │
│ 🧰 MetaMod      │ │                 │ │                    │
└──────────────────┘ └─────────────────┘ └────────────────────┘
                          │
                ┌─────────▼─────────┐
                │  GUVI Callback    │
                │  Service          │
                └───────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Groq API Key (free at [console.groq.com](https://console.groq.com))

### Installation

```bash
# Clone or navigate to the project
cd agentic_honeypot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model (optional, for NER)
python -m spacy download en_core_web_sm
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# Required:
#   - API_SECRET_KEY: Your secret API key for authentication
#   - GROQ_API_KEY: Your Groq API key
```

### Running the Server

```bash
# Start the API server
python main.py

# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Testing

```bash
# Run the test suite
python tests/test_api.py

# Or with pytest
pytest tests/ -v
```

## 📖 API Documentation

Once running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Main Endpoint

```http
POST /api/v1/analyze
Content-Type: application/json
x-api-key: YOUR_API_KEY

{
    "sessionId": "unique-session-id",
    "message": {
        "sender": "scammer",
        "text": "Your bank account will be blocked. Verify now.",
        "timestamp": "2024-01-26T10:00:00Z"
    },
    "conversationHistory": [],
    "metadata": {
        "channel": "SMS",
        "language": "English",
        "locale": "IN"
    }
}
```

### Response

```json
{
    "status": "success",
    "scamDetected": true,
    "agentResponse": "What should I do? Which bank are you from?",
    "engagementMetrics": {
        "engagementDurationSeconds": 45,
        "totalMessagesExchanged": 2
    },
    "extractedIntelligence": {
        "bankAccounts": [],
        "upiIds": [],
        "phishingLinks": [],
        "phoneNumbers": [],
        "suspiciousKeywords": ["blocked", "verify"]
    },
    "agentNotes": "Scam confirmed with 85% confidence. | Goal: build_trust",
    "councilVerdict": {
        "is_scam": true,
        "confidence": 0.85,
        "votes": [...],
        "justification": "...",
        "vote_breakdown": "..."
    }
}
```

## 🧪 Detection Council Members

| Agent | Type | Description |
|-------|------|-------------|
| 🕵️‍♂️ RuleGuard | Deterministic | Pattern matching, keyword detection, urgency indicators |
| 🧮 FastML | ML | TF-IDF + RandomForest classifier |
| 🤖 BertLite | Transformer | DistilBERT for deep semantic understanding |
| 📜 LexJudge | LLM | Groq-hosted LLaMA for reasoning-based classification |
| 🔍 OutlierSentinel | Embedding | SBERT-based anomaly detection |
| 🧵 ContextSeer | LLM+Memory | Multi-turn context analysis |
| 🧰 MetaModerator | Meta-Agent | Weighted ensemble aggregator |

## 📁 Project Structure

```
agentic_honeypot/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
│
├── config/
│   └── settings.py        # Pydantic configuration
│
├── models/
│   └── schemas.py         # Pydantic data models
│
├── agents/
│   ├── base_agent.py      # Abstract base class
│   ├── rule_guard.py      # Rule-based detection
│   ├── fast_ml.py         # ML classifier
│   ├── bert_lite.py       # Transformer model
│   ├── lex_judge.py       # LLM classifier
│   ├── outlier_sentinel.py # Anomaly detector
│   ├── context_seer.py    # Context analyzer
│   ├── meta_moderator.py  # Ensemble voter
│   └── detection_council.py # Orchestrator
│
├── engagement/
│   ├── persona_manager.py  # Victim personas
│   ├── response_generator.py # LLM response generation
│   └── engagement_graph.py  # LangGraph workflow
│
├── services/
│   ├── intelligence_extractor.py # Intel extraction
│   ├── session_manager.py  # Session state
│   └── callback_service.py # GUVI callback
│
├── core/
│   └── orchestrator.py     # Main orchestrator
│
├── api/
│   ├── honeypot.py        # Main API routes
│   └── health.py          # Health endpoints
│
└── tests/
    ├── test_api.py        # API integration tests
    └── test_agents.py     # Unit tests
```

## 🔧 Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `API_SECRET_KEY` | API authentication key | Required |
| `GROQ_API_KEY` | Groq API key | Required |
| `GROQ_MODEL_DETECTION` | Model for detection | llama-3.3-70b-versatile |
| `GROQ_MODEL_ENGAGEMENT` | Model for engagement | mixtral-8x7b-32768 |
| `SCAM_CONFIDENCE_THRESHOLD` | Scam detection threshold | 0.6 |
| `MAX_CONVERSATION_TURNS` | Max turns before callback | 20 |

## 📊 Evaluation Metrics

- **Scam Detection Accuracy**: Multi-model ensemble for high precision
- **Intelligence Extraction Rate**: Regex + NER + LLM for comprehensive extraction
- **Engagement Quality**: Persona-based natural responses
- **Callback Success**: Automatic submission with retry logic

## ⚠️ Ethical Guidelines

- ❌ No impersonation of real individuals
- ❌ No sharing of real user PII
- ❌ No illegal instructions or harassment
- ✅ Responsible data handling
- ✅ Fake placeholder data only

## 📄 License

MIT License - Built for GUVI Hackathon 2024

---

**🍯 Built with LangGraph, Groq, and FastAPI**
