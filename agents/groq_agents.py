"""
Groq Agents — Scam detection voters using Groq's fast inference API.

Implements specific voters:
- LlamaScoutVoter (Conversation Realism Specialist)
- GptOssVoter (Scam Strategy Specialist)
"""

import json
import logging
import httpx
from typing import Dict, Any, Optional

from models.schemas import CouncilVote
from config.settings import get_settings

logger = logging.getLogger(__name__)

class GroqVoter:
    """Base class for Groq-based voters."""

    def __init__(self, model_name: str, api_key: str = None):
        settings = get_settings()
        self.model = model_name
        # Prefer per-agent key if provided, otherwise fall back to shared Groq key
        self.api_key = api_key or settings.groq_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def vote(self, message: str, context: str, session_id: str, turn_count: int) -> CouncilVote:
        """Analyze message and return vote."""
        prompt = self._build_prompt(message, context, session_id, turn_count)
        
        try:
            response_json = await self._call_groq(prompt)
            # Parse strict JSON format to CouncilVote
            is_scam = response_json.get("scamDetected", False)
            return CouncilVote(
                agent_name=self.__class__.__name__,
                is_scam=is_scam,
                confidence=float(response_json.get("confidence", 0.9 if is_scam else 0.0)),
                reasoning=response_json.get("agentNotes", "No notes"),
                scam_type=response_json.get("scamType", "unknown"),
                extracted_intelligence=response_json.get("extractedIntelligence", {}),
            )
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Vote failed: {e}")
            return CouncilVote(
                agent_name=self.__class__.__name__,
                is_scam=False,
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                scam_type="unknown",
            )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        raise NotImplementedError

    async def _call_groq(self, prompt: str) -> Dict[str, Any]:
        """Call Groq API."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},  # Force JSON mode
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=self.headers,
                json=payload,
            )
            
            if response.status_code != 200:
                raise Exception(f"Groq API Error {response.status_code}: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)


class LlamaScoutVoter(GroqVoter):
    """Llama-4-Scout (Conversation Realism Specialist)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            settings.groq_model_scout,
            api_key=settings.council_llama_scout_api_key or settings.groq_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return f"""
You are LlamaScout, a high-speed conversation realism and anomaly detector.

Goal: Decide if this looks like a SCAMMER conversation and extract any concrete details that help identify or track them.

Context:
{context}

Current scammer message:
"{message}"

Respond ONLY with a single valid JSON object in this exact shape:
{{
  "sessionId": "{session_id}",
  "scamDetected": true/false,
  "confidence": 0.0-1.0,
  "scamType": "bot_like_scam" | "human_scammer" | "benign",
  "totalMessagesExchanged": {turn_count},
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": []
  }},
  "agentNotes": "1-2 lines analysing realism and why this does or does not look like a scammer."
}}
"""


class GptOssVoter(GroqVoter):
    """GPT-OSS (Scam Strategy Specialist)."""
    
    def __init__(self):
        settings = get_settings()
        # Use gpt-oss-120b for strategy unless env overrides
        super().__init__(
            "openai/gpt-oss-120b",
            api_key=settings.council_gpt_oss_api_key or settings.groq_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return f"""
You are a criminology and cyber-fraud expert specialising in scam playbooks used in India (fake KYC, bank freeze, UPI refund, lottery, RBI/income-tax threats, job scams).

Task: Identify which scam strategy is being used and pull out every useful intelligence fragment.

Context:
{context}

Current scammer message:
"{message}"

Respond ONLY with a single valid JSON object in this exact shape:
{{
  "sessionId": "{session_id}",
  "scamDetected": true/false,
  "confidence": 0.0-1.0,
  "scamType": "bank_fraud" | "upi_refund" | "lottery_reward" | "kyc_update" | "impersonation" | "job_scam" | "other",
  "totalMessagesExchanged": {turn_count},
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": []
  }},
  "agentNotes": "1-2 lines summarising the scam strategy and key red flags."
}}
"""
