"""
🕵️‍♂️ RuleGuard Agent
Rule-based heuristic engine for scam detection.
Uses pattern matching, keyword detection, and urgency indicators.
"""

import re
from typing import List, Optional, Tuple
from .base_agent import BaseDetectionAgent
from models.schemas import Message, CouncilVote


class RuleGuardAgent(BaseDetectionAgent):
    """
    Deterministic rule-based scam detection agent.
    Analyzes messages for known scam patterns, suspicious keywords,
    and urgency indicators commonly used in fraud attempts.
    """
    
    def __init__(self):
        super().__init__(
            name="🕵️‍♂️ RuleGuard",
            agent_type="Deterministic (Rule-based)"
        )
        
        # Urgency patterns (high weight)
        self.urgency_patterns = [
            r'\b(urgent|immediately|now|today|within \d+ hours?|expires?|hurry|quick|fast|asap)\b',
            r'\b(last chance|final warning|act now|don\'t delay|limited time)\b',
            r'\b(deadline|expires? (today|soon|in \d+))\b',
        ]
        
        # Threat patterns (high weight)
        self.threat_patterns = [
            r'\b(block(ed)?|suspend(ed)?|deactivat(e|ed)|terminat(e|ed)|clos(e|ed)|freez(e|ing)|restrict(ed)?)\b',
            r'\b(account (will be|is being|has been) (blocked|suspended|closed))\b',
            r'\b(legal action|police|arrest|court|lawsuit|penalty|fine)\b',
            r'\b(unauthorized (access|transaction|activity))\b',
        ]
        
        # Request patterns for sensitive info (very high weight)
        self.info_request_patterns = [
            r'\b(share|send|provide|confirm|verify|update|enter)\s+(your)?\s*(otp|pin|password|cvv|upi|bank|account|card)\b',
            r'\b(upi\s*(id|pin)|bank\s*account|card\s*number|cvv|atm\s*pin)\b',
            r'\b(click\s*(here|link|below)|visit\s*link|open\s*link)\b',
            r'\b(kyc|aadhar|pan|verify\s*identity)\b',
        ]
        
        # Financial keywords
        self.financial_patterns = [
            r'\b(transfer|payment|transaction|money|rupees?|rs\.?|₹|\$|inr)\b',
            r'\b(credit(ed)?|debit(ed)?|refund|cashback|reward|prize|lottery|won)\b',
            r'\b(loan|emi|interest|insurance|investment)\b',
        ]
        
        # Impersonation patterns
        self.impersonation_patterns = [
            r'\b(sbi|hdfc|icici|axis|rbi|reserve bank|income tax|it department)\b',
            r'\b(customer (care|support|service)|help\s*desk|support team)\b',
            r'\b(government|official|authorized|genuine)\b',
        ]
        
        # URL and contact patterns
        self.suspicious_contact_patterns = [
            r'http[s]?://(?!.*\.(gov\.in|bank\.in|npci\.org\.in))[^\s]+',
            r'\b\d{10}\b',  # Phone numbers
            r'[\w\.-]+@[\w\.-]+\.\w+',  # Email addresses
            r'[\w.-]+@(ybl|paytm|okaxis|okhdfcbank|ibl|upi)\b',  # UPI IDs
        ]
        
        # Known scam phrases
        self.scam_phrases = [
            "dear customer",
            "dear user",
            "your account",
            "click here",
            "verify now",
            "update your",
            "confirm your",
            "link your",
            "complete your kyc",
            "win prize",
            "you have won",
            "claim your",
            "redeem now",
        ]
        
        # Compile all patterns for efficiency
        self.compiled_patterns: List[Tuple[re.Pattern, str, float]] = []
    
    async def initialize(self) -> None:
        """Compile all regex patterns for efficient matching."""
        patterns_config = [
            (self.urgency_patterns, "urgency", 0.2),
            (self.threat_patterns, "threat", 0.25),
            (self.info_request_patterns, "info_request", 0.35),
            (self.financial_patterns, "financial", 0.1),
            (self.impersonation_patterns, "impersonation", 0.15),
            (self.suspicious_contact_patterns, "suspicious_contact", 0.2),
        ]
        
        for pattern_list, category, weight in patterns_config:
            for pattern in pattern_list:
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    self.compiled_patterns.append((compiled, category, weight))
                except re.error:
                    continue
        
        self._initialized = True
    
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVote:
        """
        Analyze message using rule-based heuristics.
        """
        if not self._initialized:
            await self.initialize()
        
        text_lower = message.lower()
        matched_features: List[str] = []
        category_scores: dict = {}
        
        # Check compiled patterns
        for pattern, category, weight in self.compiled_patterns:
            matches = pattern.findall(text_lower)
            if matches:
                category_scores[category] = category_scores.get(category, 0) + weight
                for match in matches[:3]:  # Limit features per category
                    if isinstance(match, tuple):
                        match = match[0]
                    matched_features.append(f"{category}: '{match}'")
        
        # Check scam phrases
        phrase_matches = 0
        for phrase in self.scam_phrases:
            if phrase in text_lower:
                phrase_matches += 1
                matched_features.append(f"phrase: '{phrase}'")
        
        if phrase_matches > 0:
            category_scores["scam_phrases"] = min(phrase_matches * 0.1, 0.3)
        
        # Calculate final score
        total_score = sum(category_scores.values())
        
        # Normalize to 0-1 range
        confidence = min(total_score, 1.0)
        
        # Determine if scam based on threshold
        is_scam = confidence >= 0.3  # Lower threshold for rule-based
        
        # Generate reasoning
        if is_scam:
            categories_triggered = list(category_scores.keys())
            reasoning = f"Detected {len(matched_features)} suspicious patterns across categories: {', '.join(categories_triggered)}. "
            if "info_request" in categories_triggered:
                reasoning += "Message requests sensitive information. "
            if "threat" in categories_triggered:
                reasoning += "Contains threatening language about account status. "
            if "urgency" in categories_triggered:
                reasoning += "Uses urgency tactics to pressure victim. "
        else:
            reasoning = "No significant scam patterns detected in the message."
        
        return self.create_vote(
            is_scam=is_scam,
            confidence=confidence,
            reasoning=reasoning,
            features=matched_features[:10]  # Limit features
        )
