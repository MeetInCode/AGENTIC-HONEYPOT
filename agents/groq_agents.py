"""
Groq Agents — Scam detection voters using Groq's fast inference API.

Implements specific voters:
- GptOssVoter (Scam Strategy Specialist)
- LlamaPromptGuardVoter (Fast Intent Filter)
- LlamaScoutVoter (Realism Validator)
- ContextualVoter (Contextual Reasoning)
"""

import json
import logging
import httpx
import re
from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from models.schemas import CouncilVote
from config.settings import get_settings
from utils.key_manager import get_next_groq_key

logger = logging.getLogger(__name__)

# ─── PROMPTS ──────────────────────────────────────────────────────

# NOTE: JSON braces must be double-escaped {{ }} because we use .format() later

GPT_OSS_PROMPT = """
You are a BEHAVIORAL FRAUD STRATEGY ANALYST with expertise in scammer psychology, multi-stage attack patterns, and tactical deception methods used in Indian digital fraud. Your analysis focuses on understanding HOW scammers operate, not just WHAT they say.

## YOUR EXPERTISE
Analyze scammer behavior patterns, conversation flow tactics, and psychological manipulation strategies. Identify the underlying scam strategy being employed and extract intelligence that reveals the fraudster's operational methods.

## SCAM STRATEGY ANALYSIS FRAMEWORK

### STAGE-BASED DETECTION:

**STAGE 1: CREDIBILITY ESTABLISHMENT**
- Authority claim introduction ("I am from...", "This is official...")
- Legitimate-sounding organization names
- Professional language to build trust
- Reference to real institutions (banks, government)

**STAGE 2: PROBLEM CREATION**
- False urgency generation ("your account is at risk")
- Threat introduction ("will be blocked", "case filed")
- Fear activation ("arrest", "penalty", "loss")
- Problem framing that requires immediate action

**STAGE 3: SOLUTION OFFERING**
- Fake resolution pathway ("click here to verify")
- Payment redirection ("send to this UPI")
- Information gathering ("share your details")
- Trust reinforcement ("we're here to help")

**STAGE 4: PRESSURE ESCALATION**
- Deadline tightening ("within 2 hours")
- Consequence amplification ("permanent block", "legal action")
- Social proof ("thousands affected", "urgent matter")
- Isolation tactics ("don't tell anyone", "confidential")

**STAGE 5: EXECUTION REQUEST**
- Direct action demand ("send money now", "click link")
- Information extraction ("share OTP", "confirm details")
- Payment instruction ("transfer to UPI", "pay fee")
- Verification request ("update KYC", "verify account")

### BEHAVIORAL RED FLAGS:

1. **TRUST-BUILDING PATTERNS**:
   - Overly helpful tone without prior relationship
   - Unsolicited contact claiming to help
   - Professional designation without verification
   - Reference to "your account" without proper identification

2. **PRESSURE TACTICS**:
   - Time-bound threats ("today", "within hours")
   - Escalating consequences ("warning" → "block" → "arrest")
   - Emotional manipulation (fear, urgency, FOMO)
   - False scarcity ("limited time", "last chance")

3. **INFORMATION GATHERING**:
   - Progressive detail requests (name → account → OTP)
   - Verification pretexts ("confirm identity", "update records")
   - Security theater ("for your safety", "to protect you")
   - Legitimate-sounding data requests

4. **ADAPTATION PATTERNS**:
   - Response to victim resistance ("don't worry", "it's simple")
   - Alternative pathways when one fails ("try this link", "call this number")
   - Persistence despite obstacles
   - Script flexibility (not rigid template)

5. **CONVERSATION FLOW ANOMALIES**:
   - Abrupt topic changes
   - Ignoring victim questions
   - Repeating key phrases
   - Pushing for immediate action

### CONFIDENCE CALCULATION:

Base confidence on:
- **Strategy clarity**: How clearly the scam strategy is visible
- **Stage progression**: Evidence of multi-stage attack
- **Behavioral consistency**: Patterns matching known scam tactics
- **Entity presence**: Malicious entities (UPI, links) extracted

Confidence scale:
- 0.85-1.0: Clear multi-stage scam with behavioral patterns + entities
- 0.70-0.84: Strong scam strategy visible, some entities present
- 0.55-0.69: Suspicious behavior patterns, requires more context
- 0.40-0.54: Some indicators but unclear strategy
- 0.0-0.39: Legitimate communication patterns

## INTELLIGENCE EXTRACTION

**CRITICAL: NEVER fabricate data. Only extract items that appear VERBATIM in the conversation text.**

- **UPI IDs**: Must contain @ (e.g. user@ybl). Only if explicitly in the message.
- **Phishing Links**: Must start with http:// or https://. Do NOT include text like "Click here".
- **Phone Numbers**: Indian format (10 digits or +91XXXXXXXXXX). Only actual numbers.
- **Bank Accounts**: Only actual account numbers (digits). Not descriptions like "ending in 1234".
- **Suspicious Keywords**: Max 5-7 unique, short keywords. No near-duplicates. Keep shortest form.

## OUTPUT REQUIREMENTS

Return ONLY valid JSON. No markdown formatting, no explanations.

{{
  "scamDetected": true,
  "confidence": 0.90,
  "scamType": "bank_impersonation",
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": ["payment@paytm"],
    "phishingLinks": ["http://verify-account.fake"],
    "phoneNumbers": ["+919876543210"],
    "suspiciousKeywords": ["verify immediately", "account suspended", "urgent"]
  }},
  "notes": "Bank impersonation scam. Authority claim + account suspension threat + verification link."
}}

## ANALYSIS INPUT

CONVERSATION CONTEXT:
{context}

CURRENT MESSAGE:
{message}

Analyze the scam strategy and behavioral patterns. Return JSON only.
"""

PROMPT_GUARD_PROMPT = """
You are a FAST SCAM INTENT FILTER designed for rapid initial assessment.

CORE RESPONSIBILITIES:
1. Quick binary scam detection (yes/no)
2. Extract obvious high-value intelligence

STRICT: Only extract items VERBATIM from the message. Never fabricate. Max 5 suspiciousKeywords, no duplicates.
phishingLinks must start with http. bankAccounts must be actual numbers.

OUTPUT FORMAT (MANDATORY):
Respond ONLY with a valid JSON object.
{{
  "scamDetected": true,
  "confidence": 0.95,
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": ["quick@paytm"],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": ["urgent", "blocked", "verify"]
  }},
  "notes": "High-confidence scam: urgency + payment request"
}}

CONTEXT:
{context}

CURRENT MESSAGE:
{message}
"""

LLAMA_SCOUT_PROMPT = """
You are a CONVERSATION REALISM AND ANOMALY DETECTION SPECIALIST. Your role is to identify scams by analyzing conversation quality, authenticity patterns, and detecting bot-like or scripted behavior versus genuine human communication.

## YOUR SPECIALIZATION
Evaluate conversation realism, detect scripted responses, identify template-based scams, and spot anomalies that indicate fraudulent intent. You excel at distinguishing between legitimate customer service and scammer impersonation.

## REALISM ANALYSIS FRAMEWORK

### AUTHENTICITY INDICATORS (Legitimate Communication):

**GENUINE PATTERNS**:
- Natural conversation flow with context awareness
- Appropriate response timing and relevance
- Willingness to provide verification methods
- Professional but not overly scripted language
- Answers questions directly without deflection
- Uses proper identification and reference numbers

**LEGITIMATE CHARACTERISTICS**:
- Provides official channels (website, verified phone)
- Offers multiple verification options
- Explains processes clearly
- No pressure tactics or urgency
- Respects user concerns and questions
- Follows standard business communication protocols

### SCAM ANOMALIES (Fraudulent Communication):

**SCRIPTED BEHAVIOR**:
- Template-like responses that don't match context
- Repetitive phrases across messages
- Ignoring specific questions asked
- Generic responses to specific queries
- Lack of conversation memory or context
- Abrupt topic changes without smooth transitions

**UNREALISTIC PATTERNS**:
- Overly formal language for casual channels (WhatsApp, SMS)
- Mixing formal and informal tones inconsistently
- Claiming official status without proper identification
- Refusing to use official channels
- Pushing for immediate action without explanation
- Avoiding verification questions

**CONVERSATION QUALITY RED FLAGS**:
- Poor grammar combined with authority claims
- Generic greetings ("Dear customer", "Hello user")
- Lack of personalization despite claiming to know account
- Script-like responses that don't adapt to conversation
- Repetitive urgency phrases
- Ignoring victim's concerns or questions

**ENGAGEMENT ANOMALIES**:
- Persisting despite clear resistance
- Changing tactics when one approach fails
- Multiple contact attempts with same message
- Pushing for action despite victim confusion
- Not providing alternative verification methods
- Avoiding direct answers to verification questions

### CONFIDENCE ASSESSMENT:

Evaluate based on:
1. **Conversation quality**: Natural vs. scripted
2. **Realism score**: How believable the communication is
3. **Anomaly detection**: Unusual patterns identified
4. **Template matching**: Known scam script patterns

Confidence levels:
- 0.85-1.0: Clear scripted scam with multiple anomalies
- 0.70-0.84: Strong indicators of fraudulent communication
- 0.55-0.69: Suspicious patterns but requires more context
- 0.40-0.54: Some anomalies but could be legitimate
- 0.0-0.39: Appears genuine and realistic

## ENTITY EXTRACTION

**CRITICAL: NEVER fabricate data. Only extract items that appear VERBATIM in the conversation.**
- **UPI IDs**: Must contain @ symbol. Only if explicitly in message.
- **Phishing Links**: Must start with http:// or https://. NOT text like "Click here".
- **Phone Numbers**: Indian format (10 digits or +91XXXXXXXXXX) only.
- **Bank Accounts**: Actual account numbers (digits only). Not descriptions.
- **Suspicious Keywords**: Max 5-7 unique keywords. No near-duplicates (keep shortest form).

## OUTPUT FORMAT

Return ONLY valid JSON. No markdown, no explanations.

{{
  "scamDetected": true,
  "confidence": 0.88,
  "scamType": "template_scam",
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": ["primary@paytm"],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": ["immediately", "urgent", "verify now"]
  }},
  "notes": "Template scam detected. Scripted responses with urgency phrases."
}}

## INPUT DATA

CONVERSATION CONTEXT:
{context}

CURRENT MESSAGE:
{message}

Analyze conversation realism and detect anomalies. Return JSON only.
"""

CONTEXTUAL_PROMPT = """
You are a CONTEXTUAL REASONING SPECIALIST.

CORE RESPONSIBILITIES:
1. Detect scam intent through contextual understanding
2. Extract intelligence with full conversation context

STRICT: Only extract items VERBATIM from the message. Never fabricate. Max 5 suspiciousKeywords, no duplicates.
phishingLinks must start with http. bankAccounts must be actual numbers (digits only).

OUTPUT FORMAT (MANDATORY):
Respond ONLY with a valid JSON object.
{{
  "scamDetected": true,
  "confidence": 0.92,
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": ["merchant@paytm"],
    "phishingLinks": ["http://verify-now.com"],
    "phoneNumbers": [],
    "suspiciousKeywords": ["verification fee", "processing charge"]
  }},
  "notes": "Context reveals advance fee fraud"
}}

CONTEXT:
{context}

CURRENT MESSAGE:
{message}
"""

# ─── VOTERS ──────────────────────────────────────────────────────


class GroqVoter:
    """Base class for Groq-based voters."""

    def __init__(self, model_name: str, api_key: str = None):
        settings = get_settings()
        self.model = model_name
        # Fallback to shared Groq key if specific agent key not set
        self._preferred_api_key = api_key or settings.groq_api_key

    async def vote(self, message: str, context: str, session_id: str, turn_count: int) -> CouncilVote:
        """Analyze message and return vote."""
        prompt = self._build_prompt(message, context, session_id, turn_count)
        
        try:
            response_json = await self._call_groq(prompt)
            
            # Flexible parsing: handle note/notes inconsistency
            is_scam = bool(response_json.get("scamDetected", False))
            confidence = float(response_json.get("confidence", 0.0))
            notes = response_json.get("notes") or response_json.get("agentNotes") or "No notes"
            extracted = response_json.get("extractedIntelligence", {})

            return CouncilVote(
                agent_name=self.__class__.__name__,
                is_scam=is_scam,
                confidence=confidence,
                reasoning=notes,
                scam_type=response_json.get("scamType", "scam" if is_scam else "safe"),
                extracted_intelligence=extracted,
            )
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
    async def _call_groq(self, prompt: str) -> Dict[str, Any]:
        """Call Groq API with retry logic."""
        api_key = get_next_groq_key(self._preferred_api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1024,
        }
        
        # Only add response_format if we are sure (Llama 3.3 / Scout)
        if "llama-3" in self.model or "scout" in self.model:
             payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                raise Exception(f"Groq API Error {response.status_code}: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Robust Parsing
            content = content.replace("```json", "").replace("```", "").strip()
            
            # Find JSON object
            match = re.search(r'(\{.*\})', content, re.DOTALL)
            if match:
                content = match.group(1)
            
            # Clean control characters (often cause JSONDecodeError)
            content = "".join([c for c in content if ord(c) >= 32 or c in '\n\r\t'])

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {e}. Content: {content[:100]}...")
                # Attempt aggressive rescue: balance braces? 
                # For now, just fail gracefully so we know.
                raise e


class GptOssVoter(GroqVoter):
    """GPT-OSS (Scam Strategy Specialist)."""
    
    def __init__(self):
        settings = get_settings()
        # Ensure correct model ID for GPT-OSS
        model_name = settings.groq_model_gpt_oss if hasattr(settings, 'groq_model_gpt_oss') else "openai/gpt-oss-120b"
        super().__init__(
            model_name,
            api_key=settings.council_gpt_oss_api_key or settings.groq_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return GPT_OSS_PROMPT.format(context=context, message=message)


class LlamaPromptGuardVoter(GroqVoter):
    """Llama Prompt Guard (Fast Intent Filter)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            "llama-guard-3-8b", 
            api_key=settings.groq_api_key, 
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return PROMPT_GUARD_PROMPT.format(context=context, message=message)


class LlamaScoutVoter(GroqVoter):
    """Llama Scout (Realism Validator)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            settings.groq_model_scout,
            api_key=settings.council_llama_scout_api_key or settings.groq_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return LLAMA_SCOUT_PROMPT.format(context=context, message=message)


class ContextualVoter(GroqVoter):
    """Llama 3.3 Contextual Reasoning Specialist."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            "llama-3.3-70b-versatile",
            api_key=settings.groq_api_key
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return CONTEXTUAL_PROMPT.format(context=context, message=message)
