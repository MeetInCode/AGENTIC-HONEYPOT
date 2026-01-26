"""
🧵 ContextSeer Agent
LLM with prior chat history for intent progression analysis.
Analyzes multi-turn conversations to detect evolving scam tactics.
"""

from typing import List, Optional
import json
from groq import AsyncGroq

from .base_agent import BaseDetectionAgent
from models.schemas import Message, CouncilVote
from config.settings import get_settings


class ContextSeerAgent(BaseDetectionAgent):
    """
    Context-aware LLM agent that analyzes conversation history
    to detect scam intent progression and tactical patterns.
    Specializes in multi-turn scam detection.
    """
    
    def __init__(self):
        super().__init__(
            name="🧵 ContextSeer",
            agent_type="LLM + Memory (Context Analysis)"
        )
        self.client: Optional[AsyncGroq] = None
        self.settings = get_settings()
        
        self.system_prompt = """You are an expert in analyzing conversation patterns to detect scam progression.

Your task is to analyze the FULL conversation context and identify:
1. **Escalation patterns**: How the conversation builds towards extracting sensitive info
2. **Trust manipulation**: Attempts to establish false credibility
3. **Topic steering**: Deliberate redirects towards financial/personal information
4. **Consistency analysis**: Contradictions or suspicious changes in narrative
5. **Intent progression**: How the sender's goals evolve across messages

Focus on Indian scams: UPI fraud, bank impersonation, KYC scams, lottery fraud.

Respond in JSON format ONLY:
{
    "is_scam": true/false,
    "confidence": 0.0-1.0,
    "intent_progression": "Description of how intent evolves across messages",
    "manipulation_tactics": ["list of tactics observed"],
    "escalation_level": "none|low|medium|high|critical",
    "next_likely_action": "Prediction of scammer's next move",
    "reasoning": "Detailed contextual analysis"
}

Consider the FULL conversation flow, not just individual messages."""
    
    async def initialize(self) -> None:
        """Initialize the Groq client."""
        try:
            self.client = AsyncGroq(api_key=self.settings.groq_api_key)
            self._initialized = True
        except Exception as e:
            self._initialized = False
    
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVote:
        """
        Analyze message with full conversation context.
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.client:
            return self._create_neutral_vote("Context analyzer not initialized")
        
        try:
            # Build conversation context
            context = self._build_conversation_context(message, conversation_history)
            
            user_prompt = f"""Analyze this conversation for scam intent progression:

CURRENT MESSAGE: "{message}"

{context}

METADATA:
- Channel: {metadata.get('channel', 'Unknown') if metadata else 'Unknown'}
- Messages in thread: {len(conversation_history) + 1 if conversation_history else 1}

Analyze the FULL conversation flow and provide your assessment in JSON format."""

            response = await self.client.chat.completions.create(
                model=self.settings.groq_model_detection,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            is_scam = result.get("is_scam", False)
            confidence = float(result.get("confidence", 0.5))
            escalation = result.get("escalation_level", "none")
            tactics = result.get("manipulation_tactics", [])
            intent_prog = result.get("intent_progression", "")
            next_action = result.get("next_likely_action", "")
            reasoning = result.get("reasoning", "")
            
            # Boost confidence based on escalation level
            escalation_boost = {
                "none": 0, "low": 0.05, "medium": 0.1, 
                "high": 0.15, "critical": 0.2
            }
            if is_scam:
                confidence = min(confidence + escalation_boost.get(escalation, 0), 1.0)
            
            # Build detailed reasoning
            full_reasoning = f"[Escalation: {escalation.upper()}] {reasoning}"
            if intent_prog:
                full_reasoning += f" Intent progression: {intent_prog}"
            if next_action:
                full_reasoning += f" Predicted next action: {next_action}"
            
            features = tactics[:5]
            if escalation != "none":
                features.insert(0, f"escalation:{escalation}")
            
            return self.create_vote(
                is_scam=is_scam,
                confidence=confidence,
                reasoning=full_reasoning,
                features=features
            )
            
        except Exception as e:
            return self._create_neutral_vote(f"Context analysis failed: {e}")
    
    def _build_conversation_context(
        self,
        current_message: str,
        history: Optional[List[Message]]
    ) -> str:
        """Build a formatted conversation context string."""
        if not history:
            return "CONVERSATION HISTORY: (This is the first message)"
        
        context_lines = ["CONVERSATION HISTORY:"]
        for i, msg in enumerate(history[-10:], 1):  # Last 10 messages
            sender = "SENDER" if msg.sender.value == "scammer" else "RECIPIENT"
            context_lines.append(f"{i}. [{sender}]: {msg.text}")
        
        return "\n".join(context_lines)
    
    def _create_neutral_vote(self, reason: str) -> CouncilVote:
        """Create a neutral vote when analysis fails."""
        return self.create_vote(
            is_scam=False,
            confidence=0.5,
            reasoning=f"Context analysis unavailable: {reason}",
            features=["context_unavailable"]
        )
