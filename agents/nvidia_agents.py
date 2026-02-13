"""
NVIDIA NIM Agents — Scam detection voters using NVIDIA's hosted models.

Implements specific voters:
- MinimaxVoter     (CM4)
- NemotronVoter    (CM3)
"""

import json
import logging
import httpx
import re
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from models.schemas import CouncilVote
from config.settings import get_settings
from utils.key_manager import get_next_nvidia_key

logger = logging.getLogger(__name__)

# ─── PROMPTS ──────────────────────────────────────────────────────

# NOTE: JSON braces must be double-escaped {{ }} because we use .format() later

MINIMAX_PROMPT_TEMPLATE = """
You are a LINGUISTIC PATTERN ANALYSIS SPECIALIST for Indian digital fraud detection. Your expertise lies in identifying scam indicators through language analysis, urgency tactics, and communication patterns specific to Indian banking and financial scams.

## YOUR ROLE
Analyze the linguistic and psychological patterns in the conversation to detect scam intent with high precision. Focus on how scammers manipulate language to create urgency, fear, and false authority.

## DETECTION FRAMEWORK

### PRIMARY INDICATORS (High Confidence Scam):
1. **URGENCY MANIPULATION**: 
   - Temporal pressure words: "immediately", "today", "within 24 hours", "right now", "urgent", "expires today"
   - Deadline creation: "last chance", "final notice", "before midnight"
   - Time-sensitive threats: "account will be blocked", "action required today"

2. **AUTHORITY IMPERSONATION**:
   - Fake official designations: "bank official", "RBI officer", "cyber crime police", "income tax department"
   - Government entity claims: "RBI", "SBI", "HDFC", "ICICI", "government department"
   - Legal threat language: "case registered", "FIR filed", "arrest warrant", "legal action"

3. **FEAR-BASED TACTICS**:
   - Account status threats: "blocked", "suspended", "frozen", "deactivated"
   - Legal consequences: "arrested", "police case", "court notice", "warrant issued"
   - Financial loss warnings: "money will be deducted", "penalty charges", "account closure"

4. **INDIAN-SPECIFIC PATTERNS**:
   - KYC/Compliance scams: "KYC expired", "update KYC", "verify Aadhar", "PAN verification"
   - UPI/Payment fraud: "UPI blocked", "payment failed", "refund processing", "settlement pending"
   - Banking terminology: "account ending", "IFSC code", "MICR code", "branch verification"

5. **LANGUAGE RED FLAGS**:
   - Hinglish code-mixing with urgency: "aapka account block ho jayega", "urgent hai", "jaldi karo"
   - Overly formal or overly casual tone mismatches
   - Grammatical errors combined with authority claims
   - Repetitive urgency phrases

### CONFIDENCE SCORING:
- 0.85-1.0: Multiple strong indicators (urgency + authority + threat)
- 0.70-0.84: Clear scam pattern with 2+ indicators
- 0.50-0.69: Suspicious but requires more context
- 0.0-0.49: Likely safe, minimal indicators

## INTELLIGENCE EXTRACTION RULES

**CRITICAL: NEVER fabricate data. Only extract items that appear VERBATIM in the conversation text.**
- **upiIds**: Must contain @ (e.g. user@ybl). Only if explicitly in message.
- **phishingLinks**: Must start with http:// or https://. Do NOT include text like "Click here" or "claim your prize".
- **phoneNumbers**: Indian format (+91XXXXXXXXXX or 10-digit starting with 6-9).
- **bankAccounts**: Only actual account numbers (digits). Not descriptions like "ending in 1234".
- **suspiciousKeywords**: Max 5-7 unique keywords. No near-duplicates (keep shortest form).

## OUTPUT REQUIREMENTS

Respond ONLY with valid JSON. No markdown, no explanations outside JSON.

{{
  "scamDetected": true,
  "confidence": 0.92,
  "scamType": "bank_impersonation",
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": ["scammer@ybl"],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": ["urgent", "account blocked", "KYC expired", "immediately"]
  }},
  "notes": "Bank impersonation scam using urgency tactics and KYC verification request."
}}

## ANALYSIS INPUT

CONVERSATION CONTEXT:
{context}

CURRENT MESSAGE TO ANALYZE:
{message}

Analyze this message using the framework above. Return JSON only.
"""

NEMOTRON_PROMPT_TEMPLATE = """
You are a COMPREHENSIVE FRAUD DETECTION ANALYST specializing in identifying all types of digital scams targeting Indian users. Your role is to perform holistic analysis combining intent detection, entity extraction, and threat assessment.

## YOUR MISSION
Conduct thorough analysis to detect scam intent and extract ALL actionable intelligence entities from the conversation. You must be precise, comprehensive, and methodical.

## DETECTION METHODOLOGY

### SCAM CLASSIFICATION FRAMEWORK:

**CATEGORY 1: FINANCIAL FRAUD**
- Payment redirection scams (UPI, bank transfer requests)
- Refund/advance fee fraud ("send money to receive refund")
- Investment scams ("guaranteed returns", "quick money")
- Loan/credit card scams ("pre-approved", "processing fee")

**CATEGORY 2: IDENTITY THEFT**
- KYC/Aadhar verification scams
- PAN card update requests
- Bank account verification
- OTP/PIN harvesting attempts

**CATEGORY 3: PHISHING & CREDENTIAL HARVESTING**
- Fake login pages (banking, UPI apps)
- Suspicious link distribution
- Email/phone verification scams
- Account recovery fraud

**CATEGORY 4: IMPERSONATION SCAMS**
- Bank official impersonation
- Government agency fraud (RBI, Income Tax, Police)
- Service provider scams (telecom, utilities)
- Tech support fraud

**CATEGORY 5: SOCIAL ENGINEERING**
- Urgency creation ("act now or lose access")
- Fear manipulation ("account blocked", "case filed")
- Trust building ("we're here to help")
- Information gathering (personal details, financial info)

### CONFIDENCE ASSESSMENT:

Evaluate based on:
1. **Clarity of scam intent** (explicit vs. implicit)
2. **Number of red flags** present
3. **Entity extraction opportunities** (UPI, links, phones)
4. **Conversation context** (first contact vs. ongoing)

Confidence ranges:
- 0.90-1.0: Explicit scam with clear malicious intent and entities
- 0.75-0.89: Strong scam indicators with multiple red flags
- 0.60-0.74: Moderate suspicion, requires careful analysis
- 0.40-0.59: Low confidence, some indicators present
- 0.0-0.39: Likely legitimate communication

## ENTITY EXTRACTION SPECIFICATIONS

**CRITICAL: NEVER fabricate data. Only extract items that appear VERBATIM in the conversation text.**

1. **UPI IDs** (`upiIds`): Must contain @ (e.g. user@ybl). Only if explicitly mentioned.
2. **Phishing Links** (`phishingLinks`): Must start with http:// or https://. Do NOT include "click here" or text descriptions.
3. **Phone Numbers** (`phoneNumbers`): Indian format +91XXXXXXXXXX or 10-digit starting with 6-9.
4. **Bank Accounts** (`bankAccounts`): Only actual account numbers (digits). Not descriptions like "ending in 1234".
5. **Suspicious Keywords** (`suspiciousKeywords`): Max 5-7 unique, short keywords. No near-duplicates (keep shortest form).

## OUTPUT FORMAT

Return ONLY valid JSON. No markdown code blocks, no explanations.

{{
  "scamDetected": true,
  "confidence": 0.95,
  "scamType": "bank_impersonation",
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": ["scammer@ybl"],
    "phishingLinks": ["https://fake-bank-verify.xyz"],
    "phoneNumbers": ["+919876543210"],
    "suspiciousKeywords": ["urgent", "KYC expired", "account blocked"]
  }},
  "notes": "Bank impersonation scam. Urgency + KYC verification request + payment redirection."
}}

## INPUT DATA

CONVERSATION HISTORY:
{context}

CURRENT MESSAGE:
{message}

Perform comprehensive analysis and return JSON only.
"""

# ─── VOTERS ──────────────────────────────────────────────────────

class NvidiaVoter:
    """Base class for NVIDIA NIM-based voters."""

    def __init__(self, model_name: str, api_key: str = None, base_url: str = None):
        settings = get_settings()
        self.model = model_name
        self.api_key = api_key or settings.nvidia_api_key
        self.base_url = base_url or settings.nvidia_base_url

    async def vote(self, message: str, context: str, session_id: str, turn_count: int) -> CouncilVote:
        """Analyze message and return vote."""
        prompt = self._build_prompt(message, context, session_id, turn_count)
        
        try:
            response_json = await self._call_nvidia(prompt)
            return self._parse_response(response_json)
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Vote failed: {e}")
            return CouncilVote(
                agent_name=self.__class__.__name__,
                is_scam=False,
                confidence=0.0,
                scam_type="error",
                reasoning=f"Error: {str(e)}",
                extracted_intelligence={},
            )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _call_nvidia(self, prompt: str) -> Dict[str, Any]:
        """Call NVIDIA NIM with retry."""
        api_key = get_next_nvidia_key(self.api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.1,
            "top_p": 1.0,
        }

        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                 raise Exception(f"NVIDIA API Error {response.status_code}: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # ─── ROBUST CLEANUP & PARSING ───
            content = content.replace("```json", "").replace("```", "").strip()
            
            # 1. Regex to extract the first { ... } block
            match = re.search(r'(\{.*\})', content, re.DOTALL)
            if match:
                content = match.group(1)

            # 2. Cleanup Control Characters (preserve newlines/tabs/spaces, remove others)
            # This handles cases where models emit invalid chars
            content = "".join([c for c in content if ord(c) >= 32 or c in '\n\r\t'])
            
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"NVIDIA JSON Parse Error: {e}. Content: {content[:150]}...")
                raise e

    def _parse_response(self, data: Dict[str, Any]) -> CouncilVote:
        """Parse JSON response to CouncilVote."""
        extracted = data.get("extractedIntelligence", {}) or {}
        
        normalized_intel = {
            "bankAccounts": extracted.get("bankAccounts", []) or [],
            "upiIds": extracted.get("upiIds", []) or [],
            "phishingLinks": extracted.get("phishingLinks", []) or [],
            "phoneNumbers": extracted.get("phoneNumbers", []) or [],
            "suspiciousKeywords": extracted.get("suspiciousKeywords", []) or [],
        }

        is_scam = bool(data.get("scamDetected", False))
        confidence = float(data.get("confidence", 0.0) or 0.0)
        notes = data.get("notes") or data.get("agentNotes") or "No notes provided"
        
        scam_type = "scam" if is_scam else "safe"
        if "scamType" in data:
             scam_type = data["scamType"]

        return CouncilVote(
            agent_name=self.__class__.__name__,
            is_scam=is_scam,
            confidence=confidence,
            reasoning=notes,
            scam_type=scam_type,
            extracted_intelligence=normalized_intel, 
        )


class MinimaxVoter(NvidiaVoter):
    """Minimax M2 (Language Pattern Specialist)."""
    
    def __init__(self):
        settings = get_settings()
        # Use updated setting for model ID
        super().__init__(
            model_name=settings.nvidia_model_minimax,
            api_key=settings.council_minimax_api_key or settings.nvidia_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return MINIMAX_PROMPT_TEMPLATE.format(context=context, message=message)


class NemotronVoter(NvidiaVoter):
    """Nemotron Super (General Scam Detection)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            model_name=settings.nvidia_model_nemotron,
            api_key=settings.council_nemotron_api_key or settings.nvidia_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return NEMOTRON_PROMPT_TEMPLATE.format(context=context, message=message)
