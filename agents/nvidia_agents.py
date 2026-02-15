"""
NVIDIA NIM Agents — Scam detection voters using NVIDIA's hosted models.

Implements specific voters:
- MinimaxVoter     (CM4)
- NemotronVoter    (CM3)
"""

import json
import os
import logging
import httpx
import re
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from models.schemas import CouncilVote
from config.settings import get_settings
from utils.key_manager import get_next_nvidia_key

logger = logging.getLogger(__name__)



# ─── VOTERS ──────────────────────────────────────────────────────

class NvidiaVoter:
    """Base class for NVIDIA NIM-based voters."""

    def __init__(self, model_name: str, prompt_file: str, api_key: str = None, base_url: str = None):
        settings = get_settings()
        self.model = model_name
        self.api_key = api_key or settings.nvidia_api_key
        self.base_url = base_url or settings.nvidia_base_url
        
        # Load prompt
        self.prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", prompt_file)
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load the prompt from the markdown file."""
        try:
            if os.path.exists(self.prompt_path):
                with open(self.prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                logger.error(f"Prompt file not found at {self.prompt_path}")
                return "You are a helpful assistant."
        except Exception as e:
            logger.error(f"Failed to load prompt: {e}")
            return "You are a helpful assistant."

    async def vote(self, message: str, context: str, session_id: str, turn_count: int) -> Optional[CouncilVote]:
        """Analyze message and return vote (or None on failure)."""
        prompt = self._build_prompt(message, context, session_id, turn_count)
        
        try:
            response_json = await self._call_nvidia(prompt)
            if not response_json:
                return None
            return self._parse_response(response_json)
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Vote failed: {e}")
            return None

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def _call_nvidia(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call NVIDIA NIM with retry (retries only on network/HTTP errors, NOT JSON parse errors)."""
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
            content = "".join([c for c in content if ord(c) >= 32 or c in '\n\r\t'])
            
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"NVIDIA JSON Parse Error: {e}. Content: {content[:150]}... Falling back to text analysis.")
                
                # Fallback: Treat the whole response as the 'notes' and try to guess scam status
                lower_content = content.lower()
                is_scam = "scam" in lower_content or "fraud" in lower_content or "suspicious" in lower_content
                
                return {
                    "scamDetected": is_scam,
                    "confidence": 0.5 if is_scam else 0.0,
                    "scamType": "potential_scam" if is_scam else "unknown",
                    "extractedIntelligence": {
                        "bankAccounts": [],
                        "upiIds": [],
                        "phishingLinks": [],
                        "phoneNumbers": [],
                        "suspiciousKeywords": ["json_parse_error"]
                    },
                    "notes": content[:1000] # Truncate to avoid huge logs
                }

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
            prompt_file="council_minimax.md",
            api_key=settings.council_minimax_api_key or settings.nvidia_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return self.prompt.format(context=context, message=message)


class NemotronVoter(NvidiaVoter):
    """Nemotron Super (General Scam Detection)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            model_name=settings.nvidia_model_nemotron,
            prompt_file="council_nemotron.md",
            api_key=settings.council_nemotron_api_key or settings.nvidia_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return self.prompt.format(context=context, message=message)
