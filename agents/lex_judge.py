"""
📜 LexJudge Agent
LLM-based text classifier using Groq-hosted models.
Provides natural language reasoning for scam detection.
"""

from typing import List, Optional
import json
from groq import Groq, AsyncGroq

from .base_agent import BaseDetectionAgent
from models.schemas import Message, CouncilVote
from config.settings import get_settings


class LexJudgeAgent(BaseDetectionAgent):
    """
    LLM-based scam detection using Groq-hosted models.
    Uses prompt engineering to classify messages and provide
    detailed reasoning for the classification decision.
    """
    
    def __init__(self):
        super().__init__(
            name="📜 LexJudge",
            agent_type="LLM (Groq - LLaMA/Mixtral)"
        )
        self.client: Optional[AsyncGroq] = None
        self.settings = get_settings()
        
        # Classification prompt template
        self.system_prompt = """You are a scam detection expert specializing in identifying fraudulent messages targeting Indian users.

Your task is to analyze messages and determine if they are scams, focusing on:
1. UPI/Bank fraud attempts
2. Phishing for sensitive information (OTP, PIN, passwords)
3. Fake lottery/prize notifications
4. Impersonation of banks, government, or companies
5. Urgency and fear tactics
6. Requests for personal/financial information

Respond in JSON format ONLY:
{
    "is_scam": true/false,
    "confidence": 0.0-1.0,
    "scam_type": "bank_fraud|phishing|lottery_scam|impersonation|urgency_scam|legitimate",
    "reasoning": "Detailed explanation of your analysis",
    "red_flags": ["list", "of", "specific", "indicators"],
    "risk_level": "low|medium|high|critical"
}

Be conservative but accurate. If uncertain, lean towards flagging suspicious messages."""
    
    async def initialize(self) -> None:
        """Initialize the Groq client."""
        try:
            self.client = AsyncGroq(api_key=self.settings.groq_api_key)
            self._initialized = True
        except Exception as e:
            self._initialized = False
            raise RuntimeError(f"Failed to initialize Groq client: {e}")
    
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVote:
        """
        Analyze message using LLM classification.
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.client:
            return self._create_error_vote("Groq client not initialized")
        
        try:
            # Build the user prompt
            user_prompt = f"""Analyze this message for scam intent:

MESSAGE: "{message}"

CONTEXT:
- Channel: {metadata.get('channel', 'Unknown') if metadata else 'Unknown'}
- Language: {metadata.get('language', 'English') if metadata else 'English'}
- Locale: {metadata.get('locale', 'IN') if metadata else 'IN'}

Provide your analysis in the specified JSON format."""

            # Add conversation history if available
            if conversation_history:
                history_text = "\n".join([
                    f"- {msg.sender}: {msg.text}" 
                    for msg in conversation_history[-5:]  # Last 5 messages
                ])
                user_prompt += f"\n\nPREVIOUS CONVERSATION:\n{history_text}"
            
            # Call Groq API
            response = await self.client.chat.completions.create(
                model=self.settings.groq_model_detection,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Extract values with defaults
            is_scam = result.get("is_scam", False)
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "No reasoning provided")
            red_flags = result.get("red_flags", [])
            scam_type = result.get("scam_type", "unknown")
            risk_level = result.get("risk_level", "medium")
            
            # Build detailed reasoning
            full_reasoning = f"[{scam_type.upper()}] {reasoning}"
            if risk_level:
                full_reasoning += f" Risk Level: {risk_level}."
            
            return self.create_vote(
                is_scam=is_scam,
                confidence=confidence,
                reasoning=full_reasoning,
                features=red_flags
            )
            
        except json.JSONDecodeError as e:
            return self._create_error_vote(f"Invalid JSON response: {e}")
        except Exception as e:
            return self._create_error_vote(f"LLM analysis failed: {e}")
    
    def _create_error_vote(self, error_msg: str) -> CouncilVote:
        """Create a neutral vote when an error occurs."""
        return self.create_vote(
            is_scam=False,
            confidence=0.5,
            reasoning=f"Analysis error: {error_msg}. Returning neutral vote.",
            features=["error_occurred"]
        )
