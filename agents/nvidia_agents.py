"""
NVIDIA NIM Agents
Implements detection agents using NVIDIA's NIM API (OpenAI-compatible).
"""

import os
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI
from rich.console import Console

from .base_agent import BaseDetectionAgent
from models.schemas import CouncilVote, Message
from config.settings import get_settings

console = Console()

class NvidiaBaseAgent(BaseDetectionAgent):
    """Base class for NVIDIA NIM-based agents."""
    
    def __init__(self, name: str, model: str, agent_type: str = "NVIDIA"):
        super().__init__(name, agent_type)
        self.output_type = "probability"
        self.settings = get_settings()
        self.model = model
        self.client: Optional[AsyncOpenAI] = None
        
    async def initialize(self) -> None:
        """Initialize the OpenAI client for NVIDIA NIM."""
        if not self.settings.nvidia_api_key:
            console.print(f"[yellow]⚠️ NVIDIA API Key not found. {self.name} will be disabled.[/yellow]")
            return
            
        self.client = AsyncOpenAI(
            base_url=self.settings.nvidia_base_url,
            api_key=self.settings.nvidia_api_key
        )
        self._initialized = True

    async def _get_chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.5) -> str:
        """Helper to get chat completion."""
        if not self.client:
            return ""
            
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=1024,
                top_p=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            console.print(f"[red]❌ {self.name} error: {str(e)}[/red]")
            raise e

    def _unknown_vote(self, reason: str) -> CouncilVote:
        return CouncilVote(
            agent_name=self.name,
            agent_type=self.agent_type,
            is_scam=False,
            confidence=0.0,
            reasoning=f"Analysis failed: {reason}",
            features=[]
        )

class NvidiaMistralAgent(NvidiaBaseAgent):
    """
    Uses Mistral Large for high-capability strategic analysis.
    Acts as a Linguistic and Strategic Analyst.
    """
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            name="🌪️ MistralLarge", 
            model=settings.nvidia_model_mistral,
            agent_type="Strategic-LLM"
        )

    async def analyze(self, message: str, conversation_history: Optional[List[Message]] = None, metadata: Optional[dict] = None) -> CouncilVote:
        if not self.client:
            return self._unknown_vote("NVIDIA API key missing")

        prompt = f"""You are a Strategic Fraud Analyst. Analyze the following message for scam patterns, linguistic manipulation, and social engineering.
        
        Message: "{message}"
        
        Is this message a scam? Answer with YES or NO and a concise explanation."""

        try:
            response = await self._get_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            is_scam = "YES" in response.upper()
            confidence = 0.9 if is_scam else 0.1 
            
            return CouncilVote(
                agent_name=self.name,
                agent_type=self.agent_type,
                is_scam=is_scam,
                confidence=confidence,
                reasoning=response,
                features=["linguistic_analysis"]
            )
        except Exception as e:
            return self._unknown_vote(str(e))

class NvidiaDeepSeekAgent(NvidiaBaseAgent):
    """
    Uses DeepSeek for scam detection.
    Standard high-performance LLM classification.
    """
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            name="🤖 DeepSeek", 
            model=settings.nvidia_model_deepseek,
            agent_type="LLM-Classifier"
        )

    async def analyze(self, message: str, conversation_history: Optional[List[Message]] = None, metadata: Optional[dict] = None) -> CouncilVote:
        if not self.client:
            return self._unknown_vote("NVIDIA API key missing")

        context = ""
        if conversation_history:
            context = "Context:\n" + "\n".join([f"{m.sender}: {m.text}" for m in conversation_history[-3:]])

        prompt = f"""Analyze this message for scam intent.
        {context}
        
        Message to Analyze: "{message}"
        
        Is this message a scam? Verify if it contains urgency, financial requests, or known patterns.
        
        Provide a final verdict (SCAM or SAFE), a confidence score (0.0-1.0), and a brief explanation."""

        try:
            response = await self._get_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            # Simple parsing of the reasoning model output
            is_scam = "SCAM" in response.upper() and "NOT SCAM" not in response.upper()
            
            # Attempt to extract confidence if explicitly stated, otherwise estimate
            confidence = 0.85 if is_scam else 0.2
            
            return CouncilVote(
                agent_name=self.name,
                agent_type=self.agent_type,
                is_scam=is_scam,
                confidence=confidence,
                reasoning=response[:500], # Truncate deep reasoning for the vote object
                features=["deepseek_analysis"]
            )
        except Exception as e:
            return self._unknown_vote(str(e))

class NvidiaGeneralAgent(NvidiaBaseAgent):
    """
    Uses Llama-3.1-405b-instruct (massive model) for high-level context understanding.
    Acts as a 'Senior Detective'.
    """
    
    def __init__(self):
        settings = get_settings()
        super().__init__(
            name="🤖 GPT-120B", 
            model=settings.nvidia_model_general,
            agent_type="sLLM"
        )

    async def analyze(self, message: str, conversation_history: Optional[List[Message]] = None, metadata: Optional[dict] = None) -> CouncilVote:
        if not self.client:
            return self._unknown_vote("NVIDIA API key missing")

        messages = [
            {"role": "system", "content": "You are a senior cyber-crime detective. Analyze the following communication for fraud."}
        ]
        
        if conversation_history:
            for msg in conversation_history[-5:]:
                messages.append({"role": "user" if msg.sender == "scammer" else "assistant", "content": msg.text})
                
        messages.append({"role": "user", "content": f"New Message: {message}\n\nIs this likely a scam? Reply JSON-formatted: {{'is_scam': bool, 'confidence': float, 'reason': str}}"})

        try:
            response = await self._get_chat_completion(messages=messages, temperature=0.2)
            
            # Basic parsing if JSON fails or model chats too much (since 405b is chatty)
            # ideally we'd use function calling or json mode, but let's do robust string parsing for now
            lower_resp = response.lower()
            is_scam = "true" in lower_resp or "'is_scam': true" in lower_resp or '"is_scam": true' in lower_resp
            
            return CouncilVote(
                agent_name=self.name,
                agent_type=self.agent_type,
                is_scam=is_scam,
                confidence=0.95 if is_scam else 0.05,
                reasoning=response[:300],
                features=["gpt120b_analysis"]
            )
        except Exception as e:
            return self._unknown_vote(str(e))


