"""
Intelligence Extraction Module.
Extracts actionable intelligence from scammer interactions.
"""

import re
from typing import List, Optional, Set
import json
from groq import AsyncGroq
import spacy
from spacy.language import Language

from models.schemas import ExtractedIntelligence, Message
from config.settings import get_settings


class IntelligenceExtractor:
    """
    Extracts intelligence from scammer messages using:
    1. Regex pattern matching
    2. NER tagging (spaCy)
    3. LLM-based extraction (Groq)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[AsyncGroq] = None
        self.nlp: Optional[Language] = None
        self._initialized = False
        
        # Regex patterns for Indian financial scam intelligence
        self.patterns = {
            "upi_id": [
                r'\b[\w.-]+@(ybl|paytm|okaxis|okhdfcbank|ibl|axl|sbi|upi|apl|rapl|ikwik|pingpay|waaxis|waicici|wahdfcbank|kmbl)\b',
                r'\b[\w.-]+@[a-z]{2,10}\b',  # Generic UPI pattern
            ],
            "phone_india": [
                r'\b(?:\+91[-\s]?)?[6-9]\d{9}\b',
                r'\b(?:0)?[6-9]\d{9}\b',
            ],
            "bank_account": [
                r'\b\d{9,18}\b',  # Account numbers
                r'\b[A-Z]{4}0[A-Z0-9]{6}\b',  # IFSC codes
            ],
            "url": [
                r'https?://[^\s<>"{}|\\^`\[\]]+',
                r'www\.[^\s<>"{}|\\^`\[\]]+',
                r'\b[a-zA-Z0-9-]+\.(com|in|org|net|co\.in|xyz|info|online|site|click|link)/[^\s]*',
            ],
            "email": [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            ],
        }
        
        # Suspicious keywords categories
        self.suspicious_keywords = {
            "urgency": ["urgent", "immediately", "now", "today", "asap", "hurry", "quick", "fast", "deadline", "expires"],
            "threat": ["blocked", "suspended", "closed", "frozen", "terminated", "deactivated", "legal", "police", "arrest"],
            "action": ["verify", "update", "confirm", "click", "share", "send", "enter", "provide", "submit"],
            "financial": ["otp", "pin", "password", "cvv", "upi", "bank", "account", "card", "kyc", "aadhar", "pan"],
            "reward": ["won", "prize", "lottery", "cashback", "reward", "refund", "bonus", "offer", "free"],
            "authority": ["sbi", "rbi", "hdfc", "icici", "axis", "government", "official", "department", "ministry"],
        }
        
        # Known scam domains (partial list)
        self.scam_domains = [
            "bit.ly", "tinyurl", "shorturl", "goo.gl",
            ".xyz", ".click", ".link", ".online", ".site",
            "forms.gle", "docs.google.com/forms",
        ]
        
        # Compile regex patterns
        self.compiled_patterns = {}
        for key, patterns in self.patterns.items():
            self.compiled_patterns[key] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    async def initialize(self) -> None:
        """Initialize extraction components."""
        if self._initialized:
            return
        
        # Initialize Groq client
        self.client = AsyncGroq(api_key=self.settings.groq_api_key)
        
        # Try to load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Model not installed, will skip NER
            self.nlp = None
        
        self._initialized = True
    
    async def extract(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None
    ) -> ExtractedIntelligence:
        """
        Extract intelligence from a message and conversation.
        
        Args:
            message: Current message to analyze
            conversation_history: Previous messages for context
            
        Returns:
            ExtractedIntelligence with all extracted data
        """
        if not self._initialized:
            await self.initialize()
        
        # Combine all text for extraction
        all_text = message
        if conversation_history:
            for msg in conversation_history:
                if msg.sender == "scammer":
                    all_text += " " + msg.text
        
        # Run all extraction methods
        regex_intel = self._extract_with_regex(all_text)
        keyword_intel = self._extract_keywords(all_text)
        
        # Optionally use LLM for complex extraction
        llm_intel = await self._extract_with_llm(all_text)
        
        # Merge all intelligence
        merged = regex_intel.merge(keyword_intel)
        if llm_intel:
            merged = merged.merge(llm_intel)
        
        # Filter out obviously fake/placeholder data
        merged = self._filter_intelligence(merged)
        
        return merged
    
    def _extract_with_regex(self, text: str) -> ExtractedIntelligence:
        """Extract intelligence using regex patterns."""
        intel = ExtractedIntelligence()
        
        # Extract UPI IDs
        for pattern in self.compiled_patterns["upi_id"]:
            matches = pattern.findall(text)
            if matches:
                # Pattern returns the domain part, need to find full match
                for match in pattern.finditer(text):
                    intel.upiIds.append(match.group().lower())
        
        # Extract phone numbers
        for pattern in self.compiled_patterns["phone_india"]:
            matches = pattern.findall(text)
            for match in matches:
                # Clean the phone number
                cleaned = re.sub(r'[^\d]', '', match)
                if len(cleaned) == 10:
                    intel.phoneNumbers.append(f"+91{cleaned}")
                elif len(cleaned) == 12 and cleaned.startswith("91"):
                    intel.phoneNumbers.append(f"+{cleaned}")
        
        # Extract URLs
        for pattern in self.compiled_patterns["url"]:
            matches = pattern.findall(text)
            for match in matches:
                # Check if it's a potentially malicious URL
                if any(domain in match.lower() for domain in self.scam_domains):
                    intel.phishingLinks.append(match)
                elif not any(safe in match.lower() for safe in ['.gov.in', 'npci.org.in', '.bank.in']):
                    intel.phishingLinks.append(match)
        
        # Extract potential bank account numbers
        for pattern in self.compiled_patterns["bank_account"]:
            matches = pattern.findall(text)
            for match in matches:
                # Filter out likely non-account numbers
                if len(match) >= 9 and len(match) <= 18:
                    # Check if it's likely an account number (not a phone or random number)
                    if not match.startswith(('6', '7', '8', '9')):  # Not a phone
                        intel.bankAccounts.append(match)
        
        # Extract emails
        for pattern in self.compiled_patterns["email"]:
            matches = pattern.findall(text)
            intel.emailAddresses.extend(matches)
        
        # Remove duplicates
        intel.upiIds = list(set(intel.upiIds))
        intel.phoneNumbers = list(set(intel.phoneNumbers))
        intel.phishingLinks = list(set(intel.phishingLinks))
        intel.bankAccounts = list(set(intel.bankAccounts))
        intel.emailAddresses = list(set(intel.emailAddresses))
        
        return intel
    
    def _extract_keywords(self, text: str) -> ExtractedIntelligence:
        """Extract suspicious keywords from text."""
        intel = ExtractedIntelligence()
        text_lower = text.lower()
        
        found_keywords: Set[str] = set()
        
        for category, keywords in self.suspicious_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    found_keywords.add(keyword)
        
        intel.suspiciousKeywords = list(found_keywords)
        return intel
    
    async def _extract_with_llm(self, text: str) -> Optional[ExtractedIntelligence]:
        """Use LLM for complex extraction."""
        if not self.client:
            return None
        
        try:
            system_prompt = """Extract financial fraud indicators from the message.
Return ONLY valid JSON with these fields:
{
    "upi_ids": ["list of UPI IDs like xyz@upi"],
    "phone_numbers": ["list of phone numbers"],
    "bank_accounts": ["list of account numbers"],
    "phishing_links": ["list of suspicious URLs"],
    "email_addresses": ["list of emails"],
    "scam_keywords": ["key suspicious phrases"]
}
Only include items actually present in the text. Use empty lists if none found."""

            response = await self.client.chat.completions.create(
                model=self.settings.groq_model_summarizer,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract from: {text[:2000]}"}  # Limit text length
                ],
                temperature=0,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return ExtractedIntelligence(
                upiIds=result.get("upi_ids", []),
                phoneNumbers=result.get("phone_numbers", []),
                bankAccounts=result.get("bank_accounts", []),
                phishingLinks=result.get("phishing_links", []),
                emailAddresses=result.get("email_addresses", []),
                suspiciousKeywords=result.get("scam_keywords", [])
            )
            
        except Exception:
            return None
    
    def _filter_intelligence(self, intel: ExtractedIntelligence) -> ExtractedIntelligence:
        """Filter out placeholder and obviously fake data."""
        # Filter UPI IDs
        intel.upiIds = [
            upi for upi in intel.upiIds
            if not any(fake in upi.lower() for fake in ['test', 'fake', 'example', 'demo', 'sample'])
        ]
        
        # Filter phone numbers - keep only Indian mobile numbers
        intel.phoneNumbers = [
            phone for phone in intel.phoneNumbers
            if len(re.sub(r'[^\d]', '', phone)) >= 10
        ]
        
        # Filter URLs - remove obviously safe ones
        safe_domains = ['.gov.in', 'google.com', 'facebook.com', 'whatsapp.com']
        intel.phishingLinks = [
            url for url in intel.phishingLinks
            if not any(safe in url.lower() for safe in safe_domains)
        ]
        
        return intel
    
    async def summarize_intelligence(
        self, 
        intel: ExtractedIntelligence
    ) -> str:
        """Generate a summary of extracted intelligence."""
        if intel.is_empty():
            return "No significant intelligence extracted."
        
        parts = []
        
        if intel.upiIds:
            parts.append(f"UPI IDs: {', '.join(intel.upiIds[:5])}")
        if intel.phoneNumbers:
            parts.append(f"Phone numbers: {', '.join(intel.phoneNumbers[:5])}")
        if intel.bankAccounts:
            parts.append(f"Bank accounts: {', '.join(intel.bankAccounts[:5])}")
        if intel.phishingLinks:
            parts.append(f"Suspicious links: {', '.join(intel.phishingLinks[:3])}")
        if intel.suspiciousKeywords:
            parts.append(f"Scam indicators: {', '.join(intel.suspiciousKeywords[:10])}")
        
        return "; ".join(parts)
