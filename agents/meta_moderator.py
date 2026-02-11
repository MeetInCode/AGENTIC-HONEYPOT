import json
import logging
import httpx
from typing import List, Dict, Any
from models.schemas import CouncilVote, CouncilVerdict
from config.settings import get_settings

logger = logging.getLogger(__name__)

JUDGE_SYSTEM = """You are the Lead Scam Intelligence Analyst.
Aggregate the reports from multiple AI agents to form a final verdict.
Your output must be the FINAL callback payload for the system."""

JUDGE_PROMPT = """
## AGENT REPORTS
{votes_text}

## CONTEXT
Session ID: {session_id}
Total Messages: {turn_count}
User Message: "{message}"

## INSTRUCTIONS
1. Analyze the agent reports. If ANY agent detected a scam, treating it as high risk.
2. Deduplicate and merge all 'extractedIntelligence'.
3. Summarize 'agentNotes' into a cohesive final note.
4. Return the FINAL JSON payload exactly as shown below.

## REQUIRED JSON OUTPUT
{{
  "sessionId": "{session_id}",
  "scamDetected": true/false,
  "totalMessagesExchanged": {turn_count},
  "extractedIntelligence": {{
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": [],
    "suspiciousKeywords": []
  }},
  "agentNotes": "1-2 lines aggregated explanation of why this is a scam, based on agent reports."
}}
"""

class JudgeAgent:
    """Aggregates council votes using NVIDIA Llama 3.1 Nemotron 70B (or 49B/51B)."""

    def __init__(self):
        settings = get_settings()
        self.model = settings.nvidia_model_judge
        # Prefer dedicated judge key, fall back to shared NVIDIA key
        self.api_key = settings.judge_agent_api_key or settings.nvidia_api_key
        self.base_url = settings.nvidia_base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def adjudication(self, message: str, votes: List[CouncilVote], session_id: str, turn_count: int) -> dict:
        """Produce the final callback JSON using NVIDIA NIM."""
        
        # Prepare inputs for the prompt
        votes_summary = []
        for v in votes:
            votes_summary.append({
                "agent": v.agent_name,
                "scamDetected": v.is_scam,
                "extractedIntelligence": v.extracted_intelligence,
                "agentNotes": v.reasoning
            })
            
        votes_json = json.dumps(votes_summary, indent=2)
        
        prompt = JUDGE_PROMPT.format(
            session_id=session_id,
            turn_count=turn_count,
            message=message,
            votes_text=votes_json
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1024,
            "temperature": 0.2, # Low temp for consistency
            "top_p": 1.0,
        }

        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                )

                if response.status_code != 200:
                    raise Exception(f"NVIDIA API Error {response.status_code}: {response.text}")

                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                
                # Clean code blocks
                import re
                content = re.sub(r"```json", "", content)
                content = re.sub(r"```", "", content).strip()
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    content = content[start:end+1]

                return json.loads(content)

        except Exception as e:
            logger.error(f"[JudgeAgent] Adjudication failed: {e}")
            # Fallback local aggregation
            return self._fallback_aggregation(votes, session_id, turn_count)

    def _fallback_aggregation(self, votes: List[CouncilVote], session_id: str, turn_count: int) -> dict:
        """Fallback logic if LLM fails."""
        scam_votes = [v for v in votes if v.is_scam]
        is_scam = len(scam_votes) > 0 # High sensitivity: if any say scam, it's scam
        
        merged_intel = {
            "bankAccounts": [], "upiIds": [], "phishingLinks": [], 
            "phoneNumbers": [], "suspiciousKeywords": []
        }
        
        # Simple merge
        for v in votes:
            intel = v.extracted_intelligence or {}
            for k, val in intel.items():
                if k in merged_intel and isinstance(val, list):
                    merged_intel[k].extend(val)
        
        # Deduplicate
        for k in merged_intel:
            merged_intel[k] = sorted(list(set(merged_intel[k])))

        return {
            "sessionId": session_id,
            "scamDetected": is_scam,
            "totalMessagesExchanged": turn_count,
            "extractedIntelligence": merged_intel,
            "agentNotes": f"Fallback: {len(scam_votes)}/{len(votes)} agents detected scam."
        }
