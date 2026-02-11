"""
NVIDIA NIM Agents — Scam detection voters using NVIDIA's hosted models.

Implements specific voters:
- NemotronVoter (Reasoning Specialist)
- DeepSeekVoter (Entity Extraction Specialist)
- MinimaxVoter (Linguistic Pattern Specialist)
"""

import json
import logging
import os
import httpx
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from models.schemas import CouncilVote
from config.settings import get_settings

logger = logging.getLogger(__name__)

class NvidiaVoter:
    """Base class for NVIDIA NIM-based voters."""

    def __init__(self, model_name: str, api_key: str = None, base_url: str = None):
        settings = get_settings()
        self.model = model_name
        # Prefer per-agent key if provided, otherwise fall back to shared NVIDIA key
        self.api_key = api_key or settings.nvidia_api_key
        self.base_url = base_url or settings.nvidia_base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def vote(self, message: str, context: str, session_id: str, turn_count: int) -> CouncilVote:
        """Analyze message and return vote."""
        prompt = self._build_prompt(message, context, session_id, turn_count)
        
        try:
            response_json = await self._call_nvidia(prompt, session_id)
            return self._parse_response(response_json)
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Vote failed: {e}")
            # Fallback
            return CouncilVote(
                agent_name=self.__class__.__name__,
                is_scam=False,
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                scam_type="unknown",
            )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        """Override in subclasses."""
        raise NotImplementedError

    async def _execute_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the HTTP call to NVIDIA NIM."""
        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            )
            
            if response.status_code != 200:
                error_body = response.text
                logger.error(f"[{self.__class__.__name__}] API Error {response.status_code}: {error_body}")
                raise Exception(f"Error code: {response.status_code} - {error_body}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Clean markdown code blocks if present
            content = content.strip()
            import re
            content = re.sub(r"```json", "", content)
            content = re.sub(r"```", "", content)
            # Remove <think> blocks
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            
            # Find JSON object
            start = content.find("{")
            end = content.rfind("}")
            
            if start != -1 and end != -1:
                content = content[start:end+1]
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.warning(f"[{self.__class__.__name__}] JSON Parse Failed. Attempting repair...")
                try:
                    repaired = self._repair_json(content)
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    logger.error(f"[{self.__class__.__name__}] Failed to parse JSON: {content[:200]}")
                    raise Exception(f"Invalid JSON response: {content[:100]}...")

    async def _call_nvidia(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """Default call method - override in subclasses for custom params."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "top_p": 1.0,
        }
        return await self._execute_call(payload)

    def _parse_response(self, data: Dict[str, Any]) -> CouncilVote:
        """
        Convert model JSON to CouncilVote.

        If the model omits fields or returns a very weak answer, we:
          - normalise extractedIntelligence
          - auto-flag as scam when any strong intelligence is present
          - generate a sensible default agentNotes
        """
        extracted = data.get("extractedIntelligence", {}) or {}
        # Normalize intelligence keys to the required schema as lists
        normalized_extracted = {
            "bankAccounts": extracted.get("bankAccounts", []) or [],
            "upiIds": extracted.get("upiIds", []) or [],
            "phishingLinks": extracted.get("phishingLinks", []) or [],
            "phoneNumbers": extracted.get("phoneNumbers", []) or [],
            "suspiciousKeywords": extracted.get("suspiciousKeywords", []) or [],
        }

        # Heuristic: if any intelligence was actually extracted, treat as likely scam
        has_intel = any(normalized_extracted[key] for key in normalized_extracted)

        raw_scam = data.get("scamDetected")
        if raw_scam is None:
            is_scam = has_intel
        else:
            is_scam = bool(raw_scam)

        # Confidence is required; if missing, infer a conservative default.
        if "confidence" in data:
            confidence = float(data.get("confidence", 0.0) or 0.0)
        else:
            # If we auto-flagged due to strong intelligence, still give non-zero confidence
            confidence = 0.9 if is_scam else (0.2 if has_intel else 0.0)

        # Agent notes — fall back to an explanation instead of "No notes provided"
        agent_notes = data.get("agentNotes")
        if not agent_notes:
            if has_intel:
                agent_notes = (
                    "Model did not provide notes; auto-flagged as scam due to extracted intelligence "
                    f"(accounts={len(normalized_extracted['bankAccounts'])}, "
                    f"upiIds={len(normalized_extracted['upiIds'])}, "
                    f"links={len(normalized_extracted['phishingLinks'])}, "
                    f"phones={len(normalized_extracted['phoneNumbers'])})."
                )
            else:
                agent_notes = "Model did not provide notes and no clear scam indicators were extracted."

        scam_type = str(
            data.get(
                "scamType",
                "scam" if is_scam else ("intel_only" if has_intel else "safe"),
            )
        )

        return CouncilVote(
            agent_name=self.__class__.__name__,
            is_scam=is_scam,
            confidence=confidence,
            reasoning=agent_notes,
            scam_type=scam_type,
            extracted_intelligence=normalized_extracted,
        )


class NemotronVoter(NvidiaVoter):
    """NVIDIA Nemotron Safety 8B (Safety Specialist)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            settings.nvidia_model_safety,
            api_key=settings.council_nemotron_api_key or settings.nvidia_api_key,
        )

    async def _call_nvidia(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """Override to set safety-specific params if needed."""
        # Safety models often prefer lower temperature
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.1, # Low temp for safety
            "top_p": 1.0,
        }
        return await self._execute_call(payload)

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return f"""
You are a bank fraud and phishing safety expert focused on Indian scam patterns.

Task: Analyse if the SCAMMER's message is part of a financial or identity scam and extract as much concrete intelligence as possible.

Context:
{context}

Current scammer message:
"{message}"

Respond ONLY with a single valid JSON object in this exact shape:
{{
  "sessionId": "{session_id}",
  "scamDetected": true/false,
  "confidence": 0.0-1.0,
  "scamType": "bank_fraud" | "upi_scam" | "kyc_phishing" | "impersonation" | "lottery_reward" | "other",
  "extractedIntelligence": {{
    "bankAccounts": ["..."],
    "upiIds": ["..."],
    "phishingLinks": ["..."],
    "phoneNumbers": ["..."],
    "suspiciousKeywords": ["..."]
  }},
  "agentNotes": "1-2 lines explaining why this is or is not a scam, in concise analyst language."
}}
"""

class MultilingualSafetyVoter(NvidiaVoter):
    """NVIDIA Nemotron Multilingual Safety Guard 8B."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            settings.nvidia_model_safety_multilingual,
            api_key=settings.council_multilingual_safety_api_key or settings.nvidia_api_key,
        )

    async def _call_nvidia(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """Safety Guard specific params."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.5, # Low temp for safety
            "top_p": 1.0,
        }
        return await self._execute_call(payload)

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return f"""
You are a multilingual fraud and safety analyst for Indian digital channels (SMS, WhatsApp, email, social).

Task: Detect scams across English, Hinglish, and Indian regional languages. Capture concrete intelligence (UPI IDs, links, numbers) even if partially obfuscated.

Context:
{context}

Current scammer message:
"{message}"

Respond ONLY with a single valid JSON object in this exact shape:
{{
  "sessionId": "{session_id}",
  "scamDetected": true/false,
  "confidence": 0.0-1.0,
  "scamType": "multilingual_scam" | "social_engineering" | "phishing" | "other",
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": []
  }},
  "agentNotes": "1-2 lines summarising multilingual safety assessment and why this is or is not a scam."
}}
"""

class MinimaxVoter(NvidiaVoter):
    """Minimax M2.1 (Linguistic Pattern Specialist)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            settings.nvidia_model_minimax,
            api_key=settings.council_minimax_api_key or settings.nvidia_api_key,
        )

    async def _call_nvidia(self, prompt: str, session_id: str) -> Dict[str, Any]:
        """Minimax parameter variations."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.7, # Slightly higher for linguistic creativity/analysis
            "top_p": 0.9,
        }
        return await self._execute_call(payload)

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return f"""
You are a linguistic forensics specialist focused on scam language: urgency, pressure, social engineering, and manipulation tactics.

Analyse ONLY the scammer's behaviour and wording in this conversation.

Context:
{context}

Current scammer message:
"{message}"

Respond ONLY with a single valid JSON object in this exact shape:
{{
  "sessionId": "{session_id}",
  "scamDetected": true/false,
  "confidence": 0.0-1.0,
  "scamType": "language_pattern_scam" | "social_engineering" | "benign",
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": []
  }},
  "agentNotes": "1-2 lines describing the scam tactics or why the language looks safe."
}}
"""
