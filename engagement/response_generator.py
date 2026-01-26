"""
Response Generator for the Engagement Agent.
Generates believable victim responses using LLM.
"""

from typing import List, Optional, Dict, Any
import json
from groq import AsyncGroq

from .persona_manager import VictimPersona
from models.schemas import Message
from config.settings import get_settings


class ResponseGenerator:
    """
    Generates believable victim responses using LLM.
    Maintains persona consistency across conversations.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[AsyncGroq] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the Groq client."""
        if self._initialized:
            return
        
        self.client = AsyncGroq(api_key=self.settings.groq_api_key)
        self._initialized = True
    
    async def generate_response(
        self,
        scammer_message: str,
        persona: VictimPersona,
        conversation_history: List[Message],
        engagement_goal: str,
        extracted_intel: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a believable victim response.
        
        Args:
            scammer_message: The latest message from the scammer
            persona: The victim persona to use
            conversation_history: Previous messages
            engagement_goal: Current goal (e.g., "elicit UPI ID")
            extracted_intel: Already extracted intelligence
            
        Returns:
            Generated response text
        """
        if not self._initialized:
            await self.initialize()
        
        # Build conversation context
        history_text = self._format_history(conversation_history)
        
        # Build dynamic instructions based on engagement goal
        goal_instruction = self._get_goal_instruction(engagement_goal, extracted_intel)
        
        system_prompt = persona.get_system_prompt()
        
        user_prompt = f"""SCAMMER'S MESSAGE: "{scammer_message}"

CONVERSATION SO FAR:
{history_text}

CURRENT GOAL: {goal_instruction}

{self._get_intel_status(extracted_intel)}

Generate your response as {persona.name}. Stay in character!
Keep response natural and concise (1-3 sentences).
Ask questions to extract more information from the scammer."""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.groq_model_engagement,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,  # Some creativity for natural responses
                max_tokens=150,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            # Fallback to a generic confused response
            return self._get_fallback_response(persona)
    
    def _format_history(self, history: List[Message]) -> str:
        """Format conversation history for the prompt."""
        if not history:
            return "(This is the start of the conversation)"
        
        lines = []
        for msg in history[-8:]:  # Last 8 messages
            role = "SCAMMER" if msg.sender.value == "scammer" else "YOU (victim)"
            lines.append(f"{role}: {msg.text}")
        
        return "\n".join(lines)
    
    def _get_goal_instruction(
        self, 
        goal: str, 
        extracted_intel: Optional[Dict[str, Any]]
    ) -> str:
        """Get specific instruction based on engagement goal."""
        goal_instructions = {
            "build_trust": "Build rapport. Sound concerned but cooperative. Don't ask for specifics yet.",
            "elicit_upi": "Try to get the scammer to share a UPI ID where you should 'send money'.",
            "elicit_bank": "Ask which bank account to use or request their account details.",
            "elicit_phone": "Try to get a phone number to 'call them back' or 'verify'.",
            "elicit_link": "Ask for a link or website to 'complete the process'.",
            "stall": "Delay the scammer. Say you need to find something or will do it later.",
            "extract_method": "Get the scammer to explain their full process/method.",
            "confirm_identity": "Ask questions to confirm who they claim to be.",
        }
        
        base_instruction = goal_instructions.get(goal, "Continue the conversation naturally.")
        
        # Add follow-up if we already have some intel
        if extracted_intel:
            if extracted_intel.get("upiIds"):
                base_instruction += " (UPI already obtained, try for bank/phone)"
            if extracted_intel.get("phoneNumbers"):
                base_instruction += " (Phone already obtained, try for links/accounts)"
        
        return base_instruction
    
    def _get_intel_status(self, intel: Optional[Dict[str, Any]]) -> str:
        """Format already extracted intelligence for context."""
        if not intel:
            return "INTELLIGENCE GATHERED: None yet"
        
        gathered = []
        if intel.get("upiIds"):
            gathered.append(f"UPI IDs: {intel['upiIds']}")
        if intel.get("phoneNumbers"):
            gathered.append(f"Phones: {intel['phoneNumbers']}")
        if intel.get("phishingLinks"):
            gathered.append(f"Links: {intel['phishingLinks']}")
        if intel.get("bankAccounts"):
            gathered.append(f"Accounts: {intel['bankAccounts']}")
        
        if gathered:
            return "INTELLIGENCE GATHERED:\n" + "\n".join(gathered)
        return "INTELLIGENCE GATHERED: None yet"
    
    def _get_fallback_response(self, persona: VictimPersona) -> str:
        """Get a fallback response when LLM fails."""
        import random
        
        fallback_responses = [
            f"I am not understanding properly. Can you explain again?",
            f"Wait, what should I do exactly?",
            f"Ok ji, please tell me step by step",
            f"I need a minute, please hold",
            f"Which account are you talking about?",
        ]
        
        if persona.confusion_phrases:
            return random.choice(persona.confusion_phrases)
        
        return random.choice(fallback_responses)
    
    async def generate_closing_response(
        self,
        persona: VictimPersona,
        max_turns_reached: bool = False
    ) -> str:
        """Generate a response to end the engagement."""
        if max_turns_reached:
            endings = [
                f"Sorry, my phone battery is low. I will call you back later.",
                f"Someone is at the door. I have to go.",
                f"I will discuss with my family and do it tomorrow.",
                f"I need to go now. Will do this later.",
            ]
        else:
            endings = [
                f"I think there is some mistake. I will go to bank directly.",
                f"Let me talk to my son first. He knows better.",
                f"I am feeling confused. Will figure it out later.",
            ]
        
        import random
        return random.choice(endings)
