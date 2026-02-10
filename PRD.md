---

# **PRD — Agentic Honeypot for Scam Detection & Intelligence Extraction**

---

## **1\. Scope & Constraints (Strict)**

This document defines a **single public REST API** that:

* Accepts incoming suspected scam messages  
* Immediately returns a human-like reply  
* Autonomously engages scammers across multiple turns  
* Detects scam intent  
* Extracts scam-related intelligence  
* Sends a **mandatory final callback** to the evaluation endpoint

Only requirements explicitly mentioned in the **official problem statement** are implemented.  
No UI, no dashboards, no external workflows, no additional features.

Source of truth: Official problem statement & callback specification .

---

## **2\. High-Level System Design (Evaluator View)**

Although internally optimized, the evaluator sees **only one API**.

POST /honeypot/message  
        |  
        \+--\> Reply Path (sync, immediate)  
        |  
        \+--\> Intelligence Path (async)  
                |  
                \+--\> LLM Council  
                |  
                \+--\> Judge LLM  
                |  
                \+--\> Local Session Store  
                |  
                \+--\> Mandatory Callback Dispatcher

**Key rule:**  
The reply is always sent **before** detection, extraction, or callback logic.

---

## **3\. Public API Specification (Strict)**

### **Endpoint**

POST /honeypot/message

### **Headers (Mandatory)**

x-api-key: \<SECRET\_API\_KEY\>  
Content-Type: application/json

Requests without a valid API key must be rejected.

---

## **4\. Input Request Format (Unchanged)**

### **4.1 First Message (New Session)**

{  
  "sessionId": "wertyu-dfghj-ertyui",  
  "message": {  
    "sender": "scammer",  
    "text": "Your bank account will be blocked today. Verify immediately.",  
    "timestamp": 1770005528731  
  },  
  "conversationHistory": \[\],  
  "metadata": {  
    "channel": "SMS",  
    "language": "English",  
    "locale": "IN"  
  }  
}

### **4.2 Follow-Up Message (Existing Session)**

{  
  "sessionId": "wertyu-dfghj-ertyui",  
  "message": {  
    "sender": "scammer",  
    "text": "Share your UPI ID to avoid account suspension.",  
    "timestamp": 1770005528731  
  },  
  "conversationHistory": \[  
    {  
      "sender": "scammer",  
      "text": "Your bank account will be blocked today. Verify immediately.",  
      "timestamp": 1770005528731  
    },  
    {  
      "sender": "user",  
      "text": "Why will my account be blocked?",  
      "timestamp": 1770005528731  
    }  
  \],  
  "metadata": {  
    "channel": "SMS",  
    "language": "English",  
    "locale": "IN"  
  }  
}

---

## **5\. Immediate API Response (Reply Path)**

### **Output Format (Mandatory)**

{  
  "status": "success",  
  "reply": "Why will my account be blocked?"  
}

### **Rules**

* Must be returned **synchronously**  
* Must be human-like  
* Must not reveal detection  
* Must not include intelligence, flags, or scores

---

## **6\. Intelligence Processing (Async Path)**

Triggered **after** the reply is sent.

### **Responsibilities**

* Scam detection  
* Scam intelligence extraction  
* Session aggregation  
* Callback decision

This path **never** affects reply latency.

---

## **7\. LLM Council (Detection \+ Extraction)**

### **Core Rule**

**Every council member independently:**

1. Detects scam intent  
2. Extracts scam intelligence

No member is “detection-only” or “extraction-only”.

---

### **Models Used**

#### **NVIDIA Build Platform**

(Source: [https://build.nvidia.com/models](https://build.nvidia.com/models))

* `nemotron-3-nano-30b-a3b`  
  → Used as **Judge LLM** (final aggregation & callback decision)  
* `minimax-m2`  
  → Scam language patterns, regional phrasing, urgency tactics  
* `deepseek-v3_2`  
  → Structured entity extraction (UPI IDs, phone numbers, links)

#### **Groq Platform**

(Source: [https://groq.com/](https://groq.com/))

* `openai/gpt-oss-120b`  
  → Scam strategy reasoning & behavioral analysis  
* `meta-llama/llama-prompt-guard-2-86m`  
  → Fast scam intent filtering  
* `meta-llama/llama-4-scout-17b-16e-instruct`  
  → Conversation realism validation  
* `llama-3.3-70b-versatile`  
  → Contextual reasoning & summarization

---

### **Council Output (Per Model)**

Each model returns:

{  
  "scamDetected": true,  
  "confidence": 0.92,  
  "extractedIntelligence": {  
    "bankAccounts": \[\],  
    "upiIds": \["scammer@upi"\],  
    "phishingLinks": \[\],  
    "phoneNumbers": \[\],  
    "suspiciousKeywords": \["urgent", "account blocked"\]  
  },  
  "notes": "Urgency-based payment redirection"  
}

---

## **8\. Judge LLM (Aggregation Logic)**

### **Model**

`nemotron-3-nano-30b-a3b`

### **Inputs**

* Outputs from all council members  
* Current session state  
* Time since last message

### **Responsibilities**

1. Aggregate scam detection decision  
2. Merge & deduplicate intelligence  
3. Track total messages exchanged  
4. Decide when engagement is complete  
5. Construct **final callback JSON**

Only the **Judge LLM** can trigger the callback.

---

## **9\. Session State Management (Redis Replaced)**

### **Replacement: In-Memory State Store \+ Timer Wheel**

Redis is replaced with a **local, in-process memory store** for lower latency and simpler deployment.

#### **Why This Is Better Here**

* No network hop  
* Sub-millisecond reads/writes  
* Session TTL is only 30 seconds  
* No durability requirement per problem statement

### **Implementation**

* In-memory hash map keyed by `sessionId`  
* High-resolution timer wheel for inactivity tracking  
* Automatic eviction after callback is sent

### **Stored State**

{  
  "lastMessageAt": 1770005528731,  
  "totalMessages": 6,  
  "scamDetected": true,  
  "extractedIntelligence": {  
    "bankAccounts": \[\],  
    "upiIds": \["scammer@upi"\],  
    "phishingLinks": \[\],  
    "phoneNumbers": \[\],  
    "suspiciousKeywords": \["urgent", "account blocked"\]  
  }  
}

---

## **10\. Callback Trigger Conditions (Strict)**

Callback is triggered when **any** is true:

* At least one of:  
  * `bankAccounts`  
  * `upiIds`  
  * `phishingLinks`  
  * `phoneNumbers`  
* OR **30 seconds of inactivity** since last message

These rules are **non-negotiable** per the problem statement .

---

## **11\. Mandatory Final Callback (Exact Format)**

### **Endpoint**

POST https://hackathon.guvi.in/api/updateHoneyPotFinalResult

### **Payload (Unchanged)**

{  
  "sessionId": "abc123-session-id",  
  "scamDetected": true,  
  "totalMessagesExchanged": 18,  
  "extractedIntelligence": {  
    "bankAccounts": \[\],  
    "upiIds": \["scammer@upi"\],  
    "phishingLinks": \[\],  
    "phoneNumbers": \[\],  
    "suspiciousKeywords": \["urgent", "verify now", "account blocked"\]  
  },  
  "agentNotes": "Scammer used urgency tactics and attempted payment redirection"  
}

Failure to send this callback **invalidates evaluation**.

---

## **12\. API Key Management**

### **Rules**

* One API key required for `/honeypot/message`  
* Separate API keys for **each LLM provider**  
* No shared keys  
* No hard-coded secrets

### **Environment Variables**

\# NVIDIA  
NVIDIA\_API\_KEY\_NEMOTRON=...  
NVIDIA\_API\_KEY\_MINIMAX=...  
NVIDIA\_API\_KEY\_DEEPSEEK=...

\# Groq  
GROQ\_API\_KEY\_GPT\_OSS=...  
GROQ\_API\_KEY\_PROMPT\_GUARD=...  
GROQ\_API\_KEY\_LLAMA\_SCOUT=...  
GROQ\_API\_KEY\_LLAMA\_70B=...

---

## **13\. End-to-End Demo Flow**

### **Step 1 — First Message Ingested**

Evaluator → `/honeypot/message`

➡ Immediate reply returned  
➡ Async intelligence pipeline starts

---

### **Step 2 — Follow-Up Message**

Evaluator sends second message with `conversationHistory`

➡ New reply returned  
➡ Council extracts UPI ID

---

### **Step 3 — Judge Aggregation**

Judge sees:

* Scam confirmed  
* `upiIds` non-empty

➡ Engagement marked complete

---

### **Step 4 — Mandatory Callback Sent**

System sends final payload to:

https://hackathon.guvi.in/api/updateHoneyPotFinalResult

Session is evicted from memory.

---

## **14\. Compliance Summary**

* ✅ Single public API  
* ✅ Immediate replies  
* ✅ Multi-turn engagement  
* ✅ Scam detection  
* ✅ Intelligence extraction  
* ✅ Mandatory callback  
* ✅ Ethical constraints enforced

---

