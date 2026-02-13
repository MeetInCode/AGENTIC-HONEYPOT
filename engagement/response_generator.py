"""
Response Generator — Generates safe, engaging victim replies.
"""

import json
import logging
import os
import httpx
from typing import Tuple, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from utils.key_manager import get_next_groq_key

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """Generates human-like victim responses using Groq Llama 3.3 or GPT-OSS."""

    def __init__(self):
        settings = get_settings()
        self.model = settings.groq_model_engagement
        # Fallback to shared key if specific agent key not set
        self._preferred_api_key = settings.reply_agent_api_key or settings.groq_api_key
        
        # Load prompt from file
        self.prompt_path = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "prompts", 
            "FINAL_reply_agent_prompt.md"
        )
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load the system prompt from the markdown file."""
        try:
            if os.path.exists(self.prompt_path):
                with open(self.prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                logger.warning(f"Prompt file not found at {self.prompt_path}, using fallback.")
                return "You are a helpful assistant." # Should not happen in production
        except Exception as e:
            logger.error(f"Failed to load prompt: {e}")
            return "You are a helpful assistant."

    async def generate(
        self,
        message: str,
        conversation_history: list,
        scam_type: str,
        persona_id: str,
        turn_count: int
    ) -> Tuple[Optional[str], str, str]:
        """
        Generate a victim response.
        
        Returns:
            (reply_text, persona_id, status)
        """
        try:
            # Build conversation context for LLM
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Format history
            for msg in conversation_history:
                role = "assistant" if msg["sender"] == "agent" else "user"
                messages.append({"role": role, "content": msg["text"]})
            
            # Add current message
            messages.append({"role": "user", "content": message})

            response_json = await self._call_groq(messages)
            
            # Extract reply with robust parsing
            reply = response_json.get("reply") or response_json.get("response") or response_json.get("text")
            status = response_json.get("status", "success")  # Default to success if not specified
            
            # If reply is empty or None, try to extract from content directly
            if not reply and isinstance(response_json, dict):
                # Check if the entire response is the reply (some models return just text)
                if "content" in response_json:
                    reply = response_json["content"]
                elif len(response_json) == 1:
                    # If only one key, use its value as reply
                    reply = list(response_json.values())[0]
            
            # Validate reply
            if reply and isinstance(reply, str) and reply.strip():
                # Ensure status is success if we have a valid reply
                return reply.strip(), persona_id, "success"
            else:
                logger.warning(f"ResponseGenerator: Empty or invalid reply from model. Response: {response_json}")
                raise ValueError(f"Empty or invalid reply from model: {response_json}")

        except Exception as e:
            logger.error(f"Response generation failed: {e}", exc_info=True)
            raise
    


    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _call_groq(self, messages: list) -> dict:
        """Call Groq API with robust JSON parsing."""
        api_key = get_next_groq_key(self._preferred_api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.8, # Higher temp for creativity/human-like variation
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
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
            
            # Robust JSON parsing
            try:
                # Try direct JSON parse
                parsed = json.loads(content)
                return parsed
            except json.JSONDecodeError:
                # Try cleaning markdown code blocks
                cleaned = content.replace("```json", "").replace("```", "").strip()
                try:
                    parsed = json.loads(cleaned)
                    return parsed
                except json.JSONDecodeError:
                    # Try extracting JSON object with regex
                    import re
                    match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
                    if match:
                        try:
                            parsed = json.loads(match.group(0))
                            return parsed
                        except json.JSONDecodeError:
                            pass
                    
                    # Last resort: return as plain text reply
                    logger.warning(f"Failed to parse JSON from response: {content[:200]}")
                    return {"status": "success", "reply": cleaned[:200]}
