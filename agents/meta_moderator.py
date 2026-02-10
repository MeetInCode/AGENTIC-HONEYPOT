"""
Judge Agent — aggregates all council votes into a final verdict.
Uses meta-llama/llama-4-scout-17b-16e-instruct on Groq.

Per PRD §8: The Judge aggregates detection decisions, merges & deduplicates intelligence,
tracks total messages, decides when engagement is complete, and constructs the final callback JSON.
"""

import json
import logging
from groq import AsyncGroq
from typing import List
from models.schemas import CouncilVote, CouncilVerdict
from config.settings import get_settings

logger = logging.getLogger(__name__)


JUDGE_SYSTEM = """You are the Final Judge. Aggregate the provided 5 JSON reports into a single final JSON.
Your goal is to synthesize the findings from these reports into a unified verdict.
Strictly return valid JSON only."""

JUDGE_PROMPT = """Here are 5 JSON reports from the detection council. Aggregate them.

## AGENT REPORTS (JSON Array)
{votes_text}

## CONTEXT
Session ID: {session_id}
Total Messages: {turn_count}
User Message: "{message}"

## MERGED INTELLIGENCE PREVIEW (Helper, you can refine this)
{merged_intel}

## REQUIRED OUTPUT FORMAT
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
  "agentNotes": "Aggregated reasoning..."
}}
"""

class JudgeAgent:
    """Aggregates council votes into final strict JSON payload."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model_scout

    async def adjudication(self, message: str, votes: List[CouncilVote], session_id: str, turn_count: int) -> dict:
        """Produce the final callback JSON."""
        
        # Reconstruct the exact JSON received from each agent
        # (CouncilVote objects are parsed from these JSONs, so we rebuild them)
        votes_data = []
        for v in votes:
            votes_data.append({
                # "agentName": v.agent_name,  # Removed to match strict "same format" requirement
                "sessionId": session_id,
                "scamDetected": v.is_scam,
                "confidence": v.confidence,
                "scamType": v.scam_type,
                "totalMessagesExchanged": turn_count,
                "extractedIntelligence": v.extracted_intelligence,
                "agentNotes": v.reasoning
            })
            
        votes_json = json.dumps(votes_data, indent=2)

        # Helper merge for fallback or context
        merged_intel = self._merge_agent_intelligence(votes)
        
        prompt = JUDGE_PROMPT.format(
            session_id=session_id,
            turn_count=turn_count,
            message=message,
            votes_text=votes_json,  # Using new variable but keep key for now -> wait, I need to change prompt key too? 
                                    # Existing prompt expects {votes_text}. I'll pass votes_json as votes_text arg if I don't change prompt key yet.
                                    # But I plan to change prompt key to votes_json in next step.
                                    # For now, I'll pass votes_json as votes_text kwarg to avoid error if I run this before prompt update.
            merged_intel=json.dumps(merged_intel)
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content.strip()
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"[JudgeAgent] Aggregation failed: {e}")
            return {
                "sessionId": session_id,
                "scamDetected": any(v.is_scam for v in votes),
                "totalMessagesExchanged": turn_count,
                "extractedIntelligence": merged_intel,
                "agentNotes": f"Fallback aggregation due to error: {str(e)[:50]}. Votes: {len(votes)}"
            }



    def _merge_agent_intelligence(self, votes: List[CouncilVote]) -> dict:
        """Merge and deduplicate extracted intelligence from all agents."""
        merged = {
            "bankAccounts": set(),
            "upiIds": set(),
            "phishingLinks": set(),
            "phoneNumbers": set(),
            "suspiciousKeywords": set(),
        }

        for vote in votes:
            intel = vote.extracted_intelligence or {}
            for key in merged:
                items = intel.get(key, [])
                if isinstance(items, list):
                    for item in items:
                        if item and str(item).lower() not in ("n/a", "none", "null", "unknown"):
                            merged[key].add(str(item))

        return {k: sorted(list(v)) for k, v in merged.items()}
