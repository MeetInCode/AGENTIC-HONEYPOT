"""
Response Generator — generates believable victim replies.
Uses openai/gpt-oss-120b on Groq exclusively (PRD requirement).

Design philosophy (Context7 research):
  The system prompt defines WHO the LLM is. The user messages are what
  the scammer says. The LLM responds AS the persona — not about the persona.
  Few-shot examples in the system prompt teach the exact texting style.
  Turn-adaptive guidance nudges behavior without breaking character.
"""

import logging
import random
from typing import List, Dict, Any
from groq import AsyncGroq
from config.settings import get_settings
from engagement.persona_manager import PersonaManager

logger = logging.getLogger(__name__)

# Fallback responses — written in Ramesh's voice, not generic chatbot language
FALLBACK_RESPONSES = [
    "sorry phone was on silent... kya bol rahe the aap?",
    "wait ek minute, Vikrant bol raha hai kuch... haan bolo",
    "hmm I didn't understand properly. can you say again plz?",
    "arey hold on, my glasses are somewhere... one sec",
    "oh accha... let me check this. wait",
    "beta my phone hanged for a moment. what you said?",
    "sir plz repeat, network was bad for a second",
    "haan ji... I was making chai. now tell me",
]

# Turn-specific nudges — these are appended to system prompt but written
# in the voice of stage directions, not instructions
TURN_GUIDANCE = {
    0: """

[SCENE: You just received this message out of nowhere. You were probably watching TV or having chai. React naturally — surprise, confusion, or mild concern. Ask who this person is. Don't comply with anything yet. Keep it to 1 line.]""",

    1: """

[SCENE: You're now talking to this person. You still don't fully understand what they want. Ask clarifying questions — "which bank?", "what happened exactly?", "who are you?". You're a bit worried but not panicking. 1-2 lines max.]""",

    2: """

[SCENE: The conversation is going on. You're starting to take them a bit seriously. Ask things a real person would ask to understand the situation — "my son handles this, should I ask him?", "where do I go to fix this?", "is there a number I can call?". These questions naturally extract information. 1-2 lines.]""",

    3: """

[SCENE: You're now somewhat engaged. You've been talking for a bit. Start asking for practical details: "ok so where I send the money?", "give me the link I will do", "what is your UPI id?", "tell me your name sir so I can tell Vikrant". You're cooperating but slow. 1-2 lines.]""",

    4: """

[SCENE: You're getting deeper into the conversation. Show a tiny bit of hesitation — your son's voice in your head saying "Papa, don't share OTP". But you don't refuse outright. "hmm wait my son told me about this... but you are from bank only na? ok tell me what to do". Still extracting info. 1-2 lines.]""",
}

# For turns 5+, use this
LATE_TURN_GUIDANCE = """

[SCENE: This has been going on for a while. You're a bit tired and flustered. You might say things like "sir jaldi bolo, I have to go for evening walk" or "ok ok I am doing... but my phone is slow". You're still cooperating but showing natural fatigue. Keep asking for details. 1-2 lines only.]"""


class ResponseGenerator:
    """Generates human-like victim responses using LLM + single persona."""

    def __init__(self):
        settings = get_settings()
        # Prefer dedicated reply agent key, fall back to shared Groq key
        api_key = settings.reply_agent_api_key or settings.groq_api_key
        self.client = AsyncGroq(api_key=api_key)
        self.model = settings.groq_model_engagement  # gpt-oss-120b
        self.persona_manager = PersonaManager()
        self._fallback_idx = 0
        logger.info(f"ResponseGenerator initialized with model: {self.model}")

    async def generate(
        self,
        message: str,
        conversation_history: List[Dict[str, Any]],
        scam_type: str = "unknown",
        persona_id: str = None,
        turn_count: int = 0,
    ) -> tuple[str, str]:
        """
        Generate a believable victim response as Ramesh Kumar.

        Args:
            message: Current scammer message
            conversation_history: Previous messages
            scam_type: Detected scam type (unused — single persona handles all)
            persona_id: Unused — single persona
            turn_count: Current turn number for turn-adaptive guidance

        Returns:
            Tuple of (response_text, persona_id_used, status)
        """
        persona_id = "ramesh_kumar"

        try:
            llm_messages = self._build_messages(message, conversation_history, turn_count)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=llm_messages,
                temperature=0.7,   # Balanced for Llama 3.3 coherence + creativity
                max_tokens=200,    # Increased for JSON overhead
                top_p=0.9,         # Standard optimized nucleus sampling
                response_format={"type": "json_object"},
            )

            import json
            content = response.choices[0].message.content.strip()
            try:
                data = json.loads(content)
                status = data.get("status", "failure")
                reply = data.get("reply")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {content}")
                # Fallback to success with content as reply if it looks like a message, or failure
                # Assuming failure if JSON is broken is safer for this requirement
                status = "failure"
                reply = None

            if status == "failure" or not reply:
                logger.info("Agent decided NOT to reply (status=failure)")
                return None, persona_id, "failure"

            # Strip any quotation marks the LLM might wrap around the response
            if reply.startswith('"') and reply.endswith('"'):
                reply = reply[1:-1]
            if reply.startswith("'") and reply.endswith("'"):
                reply = reply[1:-1]

            # Safety check: ensure response doesn't reveal detection
            if self._reveals_detection(reply):
                reply = self._get_fallback()
                logger.warning("Response revealed detection — using fallback")

            # Safety check: if response is too long, truncate to last sentence
            if len(reply) > 200:
                sentences = reply.split('.')
                reply = '.'.join(sentences[:2]).strip()
                if not reply.endswith(('.', '?', '!')):
                    reply += '...'

            logger.info(
                f"Generated response ({len(reply)} chars) as '{self.persona_manager.get_persona_name()}'"
            )
            return reply, persona_id, "success"

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return self._get_fallback(), persona_id, "success" # Fallback is usually success? Or should we fail? Default to success for robustness.

    def _build_messages(
        self,
        current_message: str,
        history: List[Dict[str, Any]],
        turn_count: int,
    ) -> List[Dict[str, str]]:
        """Build the LLM message array with persona system prompt + conversation history."""

        # Base system prompt — the persona's entire identity
        system_prompt = self.persona_manager.get_system_prompt()

        # Append turn-specific scene direction
        if turn_count in TURN_GUIDANCE:
            system_prompt += TURN_GUIDANCE[turn_count]
        else:
            system_prompt += LATE_TURN_GUIDANCE

        # JSON Format Instruction
        json_instruction = """
CRITICAL FORMAT INSTRUCTION:
You must return a valid JSON object.
Analyze if the incoming message is a likely scam or worth engaging as a honeypot.
- If YES (engage):
  {
    "status": "success",
    "reply": "your conversation response here as Ramesh"
  }
- If NO (do not engage/irrelevant/not a scam):
  {
    "status": "failure",
    "reply": null
  }

Do not include any text outside the JSON object.
"""
        messages = [{"role": "system", "content": system_prompt + "\n" + json_instruction}]

        # Add conversation history (last 8 messages — keeps context tight)
        recent_history = history[-8:] if len(history) > 8 else history
        for msg in recent_history:
            sender = msg.get("sender", "unknown")
            text = msg.get("text", "")
            if sender in ("scammer",):
                messages.append({"role": "user", "content": text})
            elif sender in ("agent", "user", "honeypot"):
                messages.append({"role": "assistant", "content": text})

        # Add current scammer message
        messages.append({"role": "user", "content": current_message})

        return messages

    def _reveals_detection(self, response: str) -> bool:
        """Check if response accidentally reveals scam detection or AI identity."""
        lower = response.lower()
        danger_phrases = [
            "scam detected", "this is a scam", "you are a scammer",
            "i know this is fraud", "i'm an ai", "i am an ai",
            "honeypot", "scam alert", "fraud alert", "scam detection",
            "i'm a bot", "i am a bot", "artificial intelligence",
            "as an ai", "i'm designed to", "my programming",
            "language model", "i don't have personal",
            "i'm an artificial", "i was designed",
            "i suspect this is", "this seems fraudulent",
        ]
        return any(phrase in lower for phrase in danger_phrases)

    def _get_fallback(self) -> str:
        """Get a fallback response in Ramesh's voice."""
        response = random.choice(FALLBACK_RESPONSES)
        return response
