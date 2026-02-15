"""
Groq Agents — Scam detection voters using Groq's fast inference API.

Implements specific voters:
- GptOssVoter (Scam Strategy Specialist)
- LlamaPromptGuardVoter (Fast Intent Filter)
- LlamaScoutVoter (Realism Validator)
- ContextualVoter (Contextual Reasoning)
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
from utils.key_manager import get_next_groq_key

logger = logging.getLogger(__name__)



# ─── VOTERS ──────────────────────────────────────────────────────


class GroqVoter:
    """Base class for Groq-based voters."""

    def __init__(self, model_name: str, prompt_file: str, api_key: str = None):
        settings = get_settings()
        self.model = model_name
        # Fallback to shared Groq key if specific agent key not set
        self._preferred_api_key = api_key or settings.groq_api_key
        
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
            response_json = await self._call_groq(prompt)
            if not response_json:
                return None
            
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
            return None

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        raise NotImplementedError

    async def _call_groq(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Groq API — no retries; council handles failures gracefully."""
        api_key = get_next_groq_key(self._preferred_api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
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
                return None


class GptOssVoter(GroqVoter):
    """GPT-OSS (Scam Strategy Specialist)."""
    
    def __init__(self):
        settings = get_settings()
        # Ensure correct model ID for GPT-OSS
        model_name = settings.groq_model_gpt_oss if hasattr(settings, 'groq_model_gpt_oss') else "openai/gpt-oss-120b"
        super().__init__(
            model_name,
            prompt_file="council_gpt_oss.md",
            api_key=settings.council_gpt_oss_api_key or settings.groq_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return self.prompt.format(context=context, message=message)


class LlamaPromptGuardVoter(GroqVoter):
    """Llama Prompt Guard (Fast Intent Filter)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            "llama-guard-3-8b", 
            prompt_file="council_prompt_guard.md",
            api_key=settings.groq_api_key, 
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return self.prompt.format(context=context, message=message)


class LlamaScoutVoter(GroqVoter):
    """Llama Scout (Realism Validator)."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            settings.groq_model_scout,
            prompt_file="council_scout.md",
            api_key=settings.council_llama_scout_api_key or settings.groq_api_key,
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return self.prompt.format(context=context, message=message)


class ContextualVoter(GroqVoter):
    """Llama 3.3 Contextual Reasoning Specialist."""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            "llama-3.3-70b-versatile",
            prompt_file="council_contextual.md",
            api_key=settings.groq_api_key
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return self.prompt.format(context=context, message=message)


class GroqCompoundVoter(GroqVoter):
    """Groq Compound Voter."""

    def __init__(self):
        settings = get_settings()
        # Default to groq/compound unless overridden
        model_name = settings.groq_model_compound if hasattr(settings, 'groq_model_compound') else "groq/compound"
        super().__init__(
            model_name,
            prompt_file="council_compound.md",
            api_key=settings.groq_api_key
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return self.prompt.format(context=context, message=message)

    async def _call_groq(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Groq API with compound_custom parameter."""
        api_key = get_next_groq_key(self._preferred_api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.73,
            "max_completion_tokens": 1024,
            "top_p": 1,
            "stop": None,
            "compound_custom": {"tools": {"enabled_tools": []}}
        }

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
            # Clean control characters
            content = "".join([c for c in content if ord(c) >= 32 or c in '\n\r\t'])

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {e}. Content: {content[:100]}...")
                return None


class QwenVoter(GroqVoter):
    """Qwen Voter (DeepSeek-R1-Distill equivalent or similar)."""

    def __init__(self):
        settings = get_settings()
        # Default to qwen/qwen3-32b unless overridden
        model_name = settings.groq_model_qwen if hasattr(settings, 'groq_model_qwen') else "qwen/qwen3-32b"
        super().__init__(
            model_name,
            prompt_file="council_qwen.md",
            api_key=settings.groq_api_key
        )

    def _build_prompt(self, message: str, context: str, session_id: str, turn_count: int) -> str:
        return self.prompt.format(context=context, message=message)

    async def _call_groq(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Groq API with response_format json_object."""
        api_key = get_next_groq_key(self._preferred_api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
            "max_completion_tokens": 4096,
            "top_p": 0.95,
            "reasoning_effort": "default",  # As requested, though might be model specific
            "response_format": {"type": "json_object"},
            "stop": None
        }

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
            
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {e}. Content: {content[:100]}...")
                return None
