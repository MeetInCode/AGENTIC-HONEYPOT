**Product Requirements Document (PRD)**
add langgraph and other details of project - https://www.langchain.com/langgraph and use groq for llm models - https://console.groq.com/docs/models and use nvidia models also https://build.nvidia.com/models 
use python libraries for ml and 
use Kaggle for datasets 


Detection Council Members (Agents)
Name	Role	Type	Output
🕵️‍♂️ RuleGuard	Rule-based heuristic engine	Deterministic	Scam (Y/N) + reasons
🧮 FastML	TF-IDF + Random Forest/SVM	ML	Probability + top features
🤖 BertLite	DistilBERT fine-tuned model	Transformer	Scam prob + saliency
📜 LexJudge	Prompted GPT-3.5/4 (text classifier)	LLM	Label + reasoning
🔍 OutlierSentinel	SBERT-based anomaly detector	Embedding distance	Outlier score
🧵 ContextSeer	LLM with prior chat history	LLM + memory	Intent progression
🧰 MetaModerator	Ensemble voter	Meta-agent	Final verdict + justification
---

### 🔍 Problem Statement

Online scammers frequently exploit channels like SMS, WhatsApp, and email to execute UPI/bank fraud and phishing attacks using dynamic, socially engineered messages. Traditional systems fail to adapt to evolving scammer behavior. We need a system that detects scam intent and autonomously engages with scammers to gather actionable intelligence without exposing itself.

Build an **LLM-powered agentic honeypot API** that classifies scam messages, launches believable conversations using agent graphs (via LangGraph), extracts intelligence (e.g., UPI IDs, phone numbers, phishing URLs), and delivers results to an evaluation endpoint.

---

### 🌟 Goals & Success Metrics

**Goals**:
- Real-time scam intent detection
- Autonomous, persona-consistent AI engagement
- Structured extraction of scammer artifacts
- Secure, scalable REST API with final result callback

**Success Metrics**:
- >90% precision in scam detection
- >70% successful intelligence extraction rate
- <2s latency for agent responses
- 100% callback submission for scam sessions

---

### 👤 User & System Personas

**External Users**:
- Scammer (adversary)
- GUVI Evaluation API

**System Components**:
- Detection Council (multi-model hybrid)
- Agentic Engagement Graph (LangGraph)
- Intelligence Extractor
- Callback Dispatcher

---

### ✅ Functional Requirements

1. **LLM Council-Based Scam Detection**:
   - Orchestrate a multi-model decision council:
     - RuleGuard: heuristic rules
     - FastML: TF-IDF + SVM (scikit-learn)
     - BertLite: DistilBERT classifier (HuggingFace)
     - LexJudge: Groq-hosted LLaMA 3 or Mixtral prompt-based classifier
     - OutlierSentinel: SBERT anomaly scorer
     - ContextSeer: Groq LLM with multi-turn context prompting
     - MetaModerator: ensemble aggregator with explanation logic
   - Each agent returns label + confidence + explanation
   - Use prompt templates for each agent in natural language
   - Final verdict with structured breakdown of votes

2. **Agentic Engagement via LangGraph**:
   - Use LangGraph (LangChain) to manage conversation state and transitions
   - Define persona state nodes with embedded instructions and goals
   - Prompt structure includes:
     - Persona profile
     - Prior chat history
     - Engagement goal (e.g., elicit UPI ID)
     - Safety constraints and disallowed responses
   - Invoke Groq-hosted Mixtral, Gemma or LLaMA models per step
   - NVIDIA models may be used for regional language handling or testing

3. **Intelligence Extraction**:
   - In-conversation extraction via LLM:
     - Prompt agent to list known UPI IDs, links, phone numbers
   - Post-processing with:
     - Regex (Python re)
     - NER tagging (spaCy, HuggingFace)
     - Summarizer LLM (Groq)

4. **API Interface**:
   - Accepts incoming JSON messages (per GUVI spec)
   - Returns structured output + council explanations + engagement metrics
   - Uses `x-api-key` and HTTPS

5. **Final Callback**:
   - POST to https://hackathon.guvi.in/api/updateHoneyPotFinalResult
   - Includes: `sessionId`, `scamDetected`, `totalMessagesExchanged`, `extractedIntelligence`, `agentNotes`

---

### 📂 Non-Functional Requirements

- Real-time LLM inference with low-latency Groq endpoints
- Support 100+ concurrent sessions without stateful backends
- Secure, rate-limited API
- Ethical boundaries:
  - No impersonation of real individuals
  - No real user PII in prompts
  - No financial transactions

---

### ✨ System Architecture Overview

- **Ingress Layer**: FastAPI gateway with API key auth
- **Detection Council**: Python orchestrator calling LLM voters
- **LangGraph Agent**: Graph of LLM-driven persona states (Groq backend)
- **LLM Providers**:
  - Groq Cloud: [Mixtral, Gemma 7B, LLaMA 3/2]
  - NVIDIA NIM: [LLaMA, Nemotron, CodeGemma]
- **Extraction Layer**: Regex + NER + summarizing LLM
- **Storage**: PostgreSQL/MongoDB (chat logs + intel)
- **Callback Queue**: Async dispatcher with retry logic

---

### 🔄 Conversation Lifecycle

1. Message received via API
2. Detection Council classifies intent via LLM agents
3. If scam:
   - Launch LangGraph AI agent
   - Engage and extract intelligence via prompts
   - On engagement end: send final callback
4. Else: drop or log benign traffic

---

### 🧠 Intelligence Extraction Scope

- UPI IDs
- Bank account numbers (masked)
- Phone numbers
- URLs / phishing domains
- Scam behavior patterns (urgency, impersonation)

---

### ✉️ Datasets & Model Training

- Use Kaggle datasets for:
  - SMS spam, phishing datasets
  - Bank fraud messages
- Generate synthetic multi-turn scams via Groq LLM prompts
- Train and validate classifiers (TF-IDF, BERT, etc.)

---

### ❌ Out-of-Scope

- Voice/call scam detection
- Session persistence or backend memory
- Real-time blocking/protection of live users

---

### ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM exposes detection | Prompt tuning + output filters |
| High latency | Groq-hosted LLMs (fast inference) |
| Prompt injection | Input sanitization + guardrails |
| Callback failure | Retry mechanism, logging |
| Overfitting rules | Use ensemble + diverse voters |

---

### 🔹 Evaluation Alignment

- Detection accuracy via LLM Council
- Persona realism via LangGraph
- Extraction precision and completeness
- Callback delivery success
- Ethical safeguards in prompt design