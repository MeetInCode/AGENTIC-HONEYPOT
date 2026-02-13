"""
Meta Moderator (The Judge) — Aggregates council votes into a final verdict.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from models.schemas import CouncilVote, CouncilVerdict
from utils.key_manager import get_next_groq_key

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """
You are producing the FINAL ASSESSMENT from agent reports for a honeypot system.

## Agent Reports
{votes_json}

## Rules
1. **scamDetected**: true if >50% agents vote scam AND at least 2 vote scam. If tied, default to false.
2. **confidence**: Average confidence of scam voters (0.0-1.0). If not scam, use 0.0-0.2.
3. **scamType**: Most common type from scam voters, or "safe".
4. **totalMessagesExchanged**: {total_msg_count}
5. **extractedIntelligence**: Merge from all agents with STRICT rules:
   - **NEVER fabricate data.** Only include items that appear VERBATIM in the original conversation MESSAGES (not from agent analysis).
   - **bankAccounts**: Only actual account numbers (digits only, e.g. "1234567890"). Do NOT include masked versions like "XXXXXXX1234" or descriptions like "ending in 1234".
   - **upiIds**: Must contain @ (e.g. user@ybl). Exclude anything without @.
   - **phishingLinks**: Must start with http:// or https://. Do NOT include text like "Click here" or "claim your prize".
   - **phoneNumbers**: Indian format only (10 digits or +91XXXXXXXXXX).
   - **suspiciousKeywords**: Max 5-7 unique keywords. Remove near-duplicates (keep shortest form).
   - **If scamDetected is false**: set suspiciousKeywords to [] (empty array).
6. **agentNotes**: 2-3 line professional summary (max 300 chars). Never mention "council", "votes", "agents", or internal processes.

## Output (ONLY valid JSON, nothing else)
{{
  "sessionId": "{session_id}",
  "scamDetected": true,
  "confidence": 0.85,
  "scamType": "payment_fraud",
  "totalMessagesExchanged": {total_msg_count},
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": ["example@ybl"],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": ["urgent", "verify"]
  }},
  "agentNotes": "Payment fraud detected. Scammer used urgency tactics requesting UPI transfer. Extracted UPI ID and suspicious keywords."
}}
"""

class JudgeAgent:
    """Aggregates multiple agent votes into a single authoritative verdict."""

    def __init__(self):
        settings = get_settings()
        self.model = settings.groq_model_judge
        # Fallback to general Groq key if judge-specific key not set
        self.api_key = settings.judge_agent_api_key or settings.groq_api_key

    async def adjudication(
        self,
        message: str,  # The last user message (for context if needed)
        votes: List[CouncilVote],
        session_id: str,
        total_msg_count: int
    ) -> Dict[str, Any]:
        """
        Aggregates votes into a final JSON payload for the callback.
        """
        # 1. Prepare input for LLM
        votes_data = [v.model_dump() for v in votes]
        prompt = JUDGE_PROMPT.format(
            votes_json=json.dumps(votes_data, indent=2),
            session_id=session_id,
            total_msg_count=total_msg_count
        )

        try:
            # 2. Call LLM for "Smart" Aggregation
            response = await self._call_groq(prompt)
            return self._sanitize_payload(response)

        except Exception as e:
            logger.warning(f"[JudgeAgent] LLM aggregation failed ({e}). Using deterministic fallback.")
            return self._fallback_aggregation(votes, session_id, total_msg_count)

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process LLM judge output to enforce strict extraction rules."""
        intel = payload.get("extractedIntelligence", {})

        # Filter bankAccounts: digits only, min 4 digits
        if "bankAccounts" in intel:
            clean = []
            for val in intel["bankAccounts"]:
                digits = ''.join(c for c in str(val) if c.isdigit())
                if len(digits) >= 4:
                    clean.append(digits)
            intel["bankAccounts"] = list(set(clean))

        # Filter upiIds: must contain @
        if "upiIds" in intel:
            intel["upiIds"] = [u for u in intel["upiIds"] if "@" in str(u)]

        # Filter phishingLinks: must start with http
        if "phishingLinks" in intel:
            intel["phishingLinks"] = [l for l in intel["phishingLinks"] if str(l).startswith("http")]

        # Filter phoneNumbers: must be mostly digits, 10+ chars
        if "phoneNumbers" in intel:
            clean = []
            for p in intel["phoneNumbers"]:
                digits = ''.join(c for c in str(p) if c.isdigit())
                if len(digits) >= 10:
                    clean.append(str(p))
            intel["phoneNumbers"] = clean

        # Cap suspiciousKeywords at 7
        if "suspiciousKeywords" in intel and len(intel["suspiciousKeywords"]) > 7:
            intel["suspiciousKeywords"] = intel["suspiciousKeywords"][:7]

        # Clear suspiciousKeywords if not scam
        if not payload.get("scamDetected", False):
            intel["suspiciousKeywords"] = []

        payload["extractedIntelligence"] = intel
        return payload

    def _fallback_aggregation(
        self,
        votes: List[CouncilVote],
        session_id: str,
        total_msg_count: int
    ) -> Dict[str, Any]:
        """
        Deterministic aggregation if LLM fails.
        """
        scam_votes = [v for v in votes if v.is_scam]
        safe_votes = [v for v in votes if not v.is_scam and v.scam_type != "error"]
        
        # Strict detection: require >50% (strict majority) AND at least 2 scam votes
        # This prevents false positives from single-agent errors or ties
        is_scam = len(scam_votes) > len(votes) / 2 and len(scam_votes) >= 2
        
        # If tied, default to safe (avoid false positives)
        if len(scam_votes) == len(safe_votes):
            is_scam = False
        
        # Max confidence from scam voters, else 0
        confidence = max([v.confidence for v in scam_votes], default=0.0) if is_scam else 0.0
        
        # Merge Intelligence
        merged_intel = {
            "bankAccounts": set(),
            "upiIds": set(),
            "phishingLinks": set(),
            "phoneNumbers": set(),
            "suspiciousKeywords": set(),
        }

        for v in votes:
            intel = v.extracted_intelligence or {}
            for key in merged_intel:
                items = intel.get(key, [])
                if items:
                    for item in items:
                        if isinstance(item, str):
                           # Basic Cleaning for Fallback
                           val = item.strip()
                           if key == "upiIds" and "@" not in val:
                               continue # Skip invalid UPI
                           if key == "phishingLinks" and not val.startswith("http"):
                               continue # Skip invalid links
                           if key == "bankAccounts":
                               # Only keep actual account numbers (digits only)
                               digits = ''.join(c for c in val if c.isdigit())
                               if len(digits) < 4:
                                   continue  # Skip noise
                               val = digits  # Use digits-only form
                           
                           merged_intel[key].add(val)

        # Logic to pick scam type (most common)
        scam_types = [v.scam_type for v in scam_votes if v.scam_type != "unknown"]
        final_scam_type = max(set(scam_types), key=scam_types.count) if scam_types else ("scam" if is_scam else "safe")

        # Convert sets to sorted lists
        final_intel = {k: sorted(list(v)) for k, v in merged_intel.items()}
        
        # Limit keywords to top 7
        if len(final_intel["suspiciousKeywords"]) > 7:
             final_intel["suspiciousKeywords"] = final_intel["suspiciousKeywords"][:7]

        # Clear suspiciousKeywords if not a scam
        if not is_scam:
            final_intel["suspiciousKeywords"] = []

        # Generate 2-3 line professional summary
        if is_scam:
            # Extract key intelligence for summary
            intel_summary = []
            if final_intel.get("upiIds"):
                intel_summary.append(f"UPI IDs: {', '.join(final_intel['upiIds'][:2])}")
            if final_intel.get("phishingLinks"):
                intel_summary.append(f"Phishing links: {len(final_intel['phishingLinks'])} detected")
            if final_intel.get("phoneNumbers"):
                intel_summary.append(f"Phone numbers: {len(final_intel['phoneNumbers'])} extracted")
            
            # Get primary scam type and tactic
            scam_type_desc = final_scam_type.replace("_", " ").title()
            reasons = [v.reasoning for v in scam_votes if v.reasoning][:2]
            primary_tactic = reasons[0][:100] if reasons else "Suspicious activity detected"
            
            # Build 2-3 line summary
            notes_lines = [
                f"{scam_type_desc} detected. {primary_tactic}.",
                f"Key threats: {', '.join(intel_summary[:3]) if intel_summary else 'Suspicious keywords and patterns identified'}."
            ]
            
            # Add third line if we have confidence info
            if confidence >= 0.8:
                notes_lines.append("High confidence scam with clear malicious intent.")
            
            notes = " ".join(notes_lines)
            # Ensure max 300 chars
            if len(notes) > 300:
                notes = notes[:297] + "..."
        else:
            # Safe case: 2-3 line summary
            notes_lines = [
                "Analysis indicates the conversation is likely safe.",
                "No suspicious patterns, urgency tactics, or malicious entities detected."
            ]
            # Check if there are any keywords (even in safe cases)
            if final_intel.get("suspiciousKeywords"):
                notes_lines.append("Standard communication observed with minimal risk indicators.")
            
            notes = " ".join(notes_lines)
            # Ensure max 300 chars
            if len(notes) > 300:
                notes = notes[:297] + "..."

        return {
            "sessionId": session_id,
            "scamDetected": is_scam,
            "confidence": confidence,
            "scamType": final_scam_type,
            "totalMessagesExchanged": total_msg_count,
            "extractedIntelligence": final_intel,
            "agentNotes": notes,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _call_groq(self, prompt: str) -> Dict[str, Any]:
        """Call Groq API (Llama 3.1 8b Instant) for aggregation."""
        api_key = get_next_groq_key(self.api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"}
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
            # Regex to find JSON block
            match = re.search(r'(\{.*\})', content, re.DOTALL)
            if match:
                content = match.group(1)
            else:
                # If regex fails, try parsing the whole content
                pass
            
            return json.loads(content)
