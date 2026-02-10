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
        super().__init__(settings.groq_model_scout)

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return f"""
You are LlamaScout, analyzing conversation realism.
Is this a bot/scammer or a human?

Context: {context}
Message: "{message}"

Return EXACTLY this JSON structure:
{{
  "sessionId": "{session_id}",
  "scamDetected": true/false,
  "confidence": 0.0-1.0,
  "scamType": "type",
  "totalMessagesExchanged": {turn_count},
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": []
  }},
  "agentNotes": "Realism analysis reasoning"
}}
"""


class GptOssVoter(GroqVoter):
    """GPT-OSS (Scam Strategy Specialist)."""
    
    def __init__(self):
        # Fallback to defaults if env not set, but orchestrator sets it
        settings = get_settings()
        # Use gpt-oss-120b for strategy unless env overrides
        super().__init__("openai/gpt-oss-120b") 

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return f"""
You are a Criminology Expert analyzing scam strategies.

Context: {context}
Message: "{message}"

Return JSON:
{{
  "sessionId": "{session_id}",
  "scamDetected": true/false,
  "confidence": 0.0-1.0,
  "scamType": "type",
  "totalMessagesExchanged": {turn_count},
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": []
  }},
  "agentNotes": "Strategy analysis reasoning"
}}
"""
