"""
Intelligence Extractor — regex + LLM-based extraction of scam indicators.
"""

import re
import json
import logging
from typing import Dict, Any, List
from config.settings import get_settings
from utils.key_manager import get_next_groq_key, get_groq_client

logger = logging.getLogger(__name__)


# ─── Regex Patterns ───────────────────────────────────────────────

UPI_PATTERN = re.compile(r'[a-zA-Z0-9._-]+@[a-zA-Z]{2,}', re.IGNORECASE)
PHONE_PATTERN = re.compile(r'(?:\+91[-\s]?)?(?:0)?[6-9]\d{9}')
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+|'
    r'(?:www\.)[^\s<>"\']+|'
    r'[a-zA-Z0-9-]+\.(?:xyz|tk|ml|ga|cf|gq|top|click|link|info|online|site|live|ru)[/\w.-]*',
    re.IGNORECASE
)
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
BANK_ACCOUNT_PATTERN = re.compile(r'\b\d{9,18}\b')

# Known legitimate UPI handles to filter out
LEGIT_UPI_SUFFIXES = {'@upi', '@ybl', '@paytm', '@okaxis', '@okhdfcbank', '@okicici', '@oksbi'}

# Suspicious keywords
SCAM_KEYWORDS = [
    # Urgency
    'urgent', 'immediately', 'expires today', 'last chance', 'hurry', 'blocked',
    # Threats
    'arrested', 'police', 'legal action', 'case registered', 'cyber crime',
    # Financial
    'otp', 'cvv', 'pin', 'aadhar', 'aadhaar', 'pan card', 'kyc', 'upi',
    'bank details', 'account number', 'transfer', 'refund',
    # Rewards
    'lottery', 'winner', 'prize', 'cashback', 'congratulations', 'won',
    # Authority
    'rbi', 'income tax', 'sbi', 'hdfc', 'icici', 'customer care',
]


LLM_EXTRACTION_SYSTEM = """You are a forensic intelligence analyst specialised in extracting actionable scam indicators from **Indian digital fraud communications** (SMS, WhatsApp, email, chat).

Your job is to help a honeypot system that:
- Detects scam intent
- Engages scammers without revealing detection
- Extracts intelligence for a mandatory final callback to an evaluation API

You must be extremely thorough — **every** UPI ID, phone number, URL, bank account number,
case ID, and authority name can matter.

Entity types you extract:
- UPI IDs: format user@handle (handles: @ybl, @paytm, @okaxis, @okhdfcbank, @okicici, @oksbi, @upi, @apl, @ibl, plus any custom handle like claim.prize@ybl, rbi.safe@axis)
- Phone numbers: Indian format +91-XXXXXXXXXX or 10-digit starting with 6-9
- Bank accounts: 9-18 digit account numbers, IFSC codes (format: ABCD0XXXXXX)
- Phishing links: suspicious URLs, especially non-official domains (.xyz, .tk, .ml, .click, shortened URLs, fake-bank domains)
- Email addresses: associated with scam communications
- Scammer identifiers: names, designations, fake departments, badge/ID numbers (e.g. "Officer Rahul", "Cyber Crime Division", "Inspector Vikram", "Case #CC-2024-8845")
- Keywords: urgency words, threats, authority claims, sensitive data requests (KYC, OTP, PIN, CVV, Aadhar, PAN, refunds, "account blocked", "KYC expired", "FIR", "warrant")

Always respond with valid JSON only. Never invent entities that do not appear in the conversation."""

LLM_EXTRACTION_PROMPT = """Extract **ALL** scam-related intelligence from this conversation. Be meticulous — every real-world identifier matters for tracking scammers.

## CONVERSATION
{messages}

## EXTRACTION EXAMPLE

Conversation:
[scammer]: Hello, this is Officer Rahul from Cyber Crime Division. Case #CC-2024-8845 filed against your Aadhar.
[victim]: What? Which case?
[scammer]: Your Aadhar linked to money laundering. Pay Rs 25,000 penalty immediately. Send to fix.case@ybl or call 9876543210.
[victim]: I don't understand, how do I pay?
[scammer]: Go to this link http://cybercase-pay.xyz/settle and enter your details. Do it within 1 hour or arrest warrant.

Extraction: {{
  "upiIds": ["fix.case@ybl"],
  "phoneNumbers": ["9876543210"],
  "bankAccounts": [],
  "phishingLinks": ["http://cybercase-pay.xyz/settle"],
  "emailAddresses": [],
  "suspiciousKeywords": ["Cyber Crime Division", "case filed", "Aadhar", "money laundering", "penalty", "arrest warrant"],
  "scammerIdentifiers": ["Officer Rahul", "Cyber Crime Division", "Case #CC-2024-8845"]
}}

## YOUR EXTRACTION
Extract every identifiable entity from the conversation above. Only include items ACTUALLY present — use empty arrays if nothing is found. Respond with ONLY valid JSON:
{{
  "upiIds": [],
  "phoneNumbers": [],
  "bankAccounts": [],
  "phishingLinks": [],
  "emailAddresses": [],
  "suspiciousKeywords": [],
  "scammerIdentifiers": []
}}"""


class IntelligenceExtractor:
    """Extracts actionable intelligence from scammer interactions."""

    def __init__(self):
        settings = get_settings()
        # Prefer shared Groq key as fallback; rotation pool is handled centrally.
        self._preferred_api_key = settings.groq_api_key
        self.model = settings.groq_model_scout  # llama-4-scout

    async def extract(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract intelligence from conversation messages using regex + LLM.
        
        Args:
            messages: List of message dicts with 'sender' and 'text' keys
            
        Returns:
            Dict with extracted intelligence fields
        """
        # Combine all message texts
        all_text = " ".join(m.get("text", "") for m in messages)

        # Step 1: Regex extraction (fast, reliable)
        regex_intel = self._regex_extract(all_text)
        
        # Step 2: LLM extraction (catches what regex misses)
        llm_intel = await self._llm_extract(messages)

        # Merge results (deduplicate)
        merged = self._merge_intelligence(regex_intel, llm_intel)
        
        logger.info(f"Intelligence extracted: {sum(len(v) for v in merged.values() if isinstance(v, list))} items")
        return merged

    def _regex_extract(self, text: str) -> Dict[str, Any]:
        """Extract intelligence using regex patterns."""
        upi_ids = list(set(UPI_PATTERN.findall(text)))
        # Filter: keep only if it looks like a real UPI (has @ and suffix)
        upi_ids = [u for u in upi_ids if '@' in u and not u.endswith('.com') and not u.endswith('.xyz')]
        
        phone_numbers = list(set(PHONE_PATTERN.findall(text)))
        # Filter: must be 10+ digits
        phone_numbers = [p.strip() for p in phone_numbers if len(re.sub(r'\D', '', p)) >= 10]

        urls = list(set(URL_PATTERN.findall(text)))
        emails = list(set(EMAIL_PATTERN.findall(text)))
        # Remove emails that are also counted as UPI IDs
        emails = [e for e in emails if e not in upi_ids]

        bank_accounts = list(set(BANK_ACCOUNT_PATTERN.findall(text)))
        # Filter: only clearly long numbers (12+ digits to avoid false positives)
        bank_accounts = [b for b in bank_accounts if len(b) >= 12]

        keywords_found = [kw for kw in SCAM_KEYWORDS if kw.lower() in text.lower()]

        return {
            "upiIds": upi_ids,
            "phoneNumbers": phone_numbers,
            "bankAccounts": bank_accounts,
            "phishingLinks": urls,
            "emailAddresses": emails,
            "suspiciousKeywords": keywords_found,
            "scammerIdentifiers": [],
        }

    async def _llm_extract(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract intelligence using LLM."""
        try:
            msg_text = "\n".join(
                f"[{m.get('sender', 'unknown')}]: {m.get('text', '')}"
                for m in messages
            )

            # Rotate Groq API key and get pooled client for extraction calls.
            api_key = get_next_groq_key(self._preferred_api_key)
            client = get_groq_client(api_key)

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": LLM_EXTRACTION_SYSTEM},
                    {"role": "user", "content": LLM_EXTRACTION_PROMPT.format(messages=msg_text)},
                ],
                temperature=0.1,
                # Extraction JSON is compact; keep token limit modest for speed.
                max_tokens=400,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content.strip()
            return json.loads(content)

        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return {}

    def _merge_intelligence(
        self, regex_intel: Dict[str, Any], llm_intel: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge regex and LLM results, deduplicating."""
        merged = {}
        all_keys = ["upiIds", "phoneNumbers", "bankAccounts", "phishingLinks",
                     "emailAddresses", "suspiciousKeywords", "scammerIdentifiers"]

        for key in all_keys:
            regex_items = set(regex_intel.get(key, []))
            llm_items = set(llm_intel.get(key, []))
            # Filter out placeholder/dummy data from LLM
            combined = regex_items | llm_items
            combined = {
                item for item in combined
                if item and item.lower() not in (
                    'n/a', 'none', 'null', 'unknown', 'not found',
                    'example@email.com', 'user@example.com',
                )
            }
            merged[key] = sorted(list(combined))

        return merged
