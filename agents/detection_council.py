"""
Detection Council — orchestrates 5 voters + 1 judge.

Voters (run in parallel):
  1. NemotronVoter   (NVIDIA)
  2. DeepSeekVoter   (NVIDIA)
  3. MinimaxVoter    (NVIDIA)
  4. LlamaScoutVoter (Groq)
  5. GptOssVoter     (Groq)

Judge:
  JudgeAgent (Groq, llama-4-scout)
"""

import asyncio
import logging
import time
from typing import List
from models.schemas import CouncilVote, CouncilVerdict
from agents.nvidia_agents import NemotronVoter, DeepSeekVoter, MinimaxVoter
from agents.groq_agents import LlamaScoutVoter, GptOssVoter
from agents.meta_moderator import JudgeAgent
from utils.rich_printer import print_council_votes, print_judge_verdict

logger = logging.getLogger(__name__)


class DetectionCouncil:
    """Runs 5 detection voters in parallel, then passes results to a judge."""

    def __init__(self):
        # Initialize all voters
        self.voters = [
            NemotronVoter(),
            DeepSeekVoter(),
            MinimaxVoter(),
            LlamaScoutVoter(),
            GptOssVoter(),
        ]
        self.judge = JudgeAgent()
        logger.info(f"Detection Council initialized with {len(self.voters)} voters")

    async def analyze(self, message: str, context: str = "No prior context", session_id: str = "unknown", turn_count: int = 0) -> CouncilVerdict:
        """
        Run all voters in parallel, collect votes, and pass to judge.
        
        Args:
            message: The incoming message text to analyze
            context: Summary of conversation history
            session_id: The active session ID
            turn_count: Current conversation turn
            
        Returns:
            CouncilVerdict with final scam determination
        """
        start_time = time.time()

        # Run all voters in parallel
        vote_tasks = [voter.vote(message, context, session_id, turn_count) for voter in self.voters]
        votes: List[CouncilVote] = await asyncio.gather(*vote_tasks, return_exceptions=True)

        # Filter out exceptions, keep valid votes
        valid_votes = []
        for i, vote in enumerate(votes):
            if isinstance(vote, Exception):
                logger.error(f"Voter {self.voters[i].__class__.__name__} failed: {vote}")
                # Create a fallback abstain vote
                valid_votes.append(CouncilVote(
                    agent_name=self.voters[i].__class__.__name__,
                    is_scam=False,
                    confidence=0.0,
                    reasoning=f"Voter error: {str(vote)[:100]}",
                ))
            else:
                valid_votes.append(vote)

        voting_elapsed = time.time() - start_time

        # ── Rich Print: Council Votes ──
        print_council_votes(valid_votes, voting_elapsed)

        # Pass to judge for final verdict
        # 3. Judge Aggregation (Simulated for speed or LLM)
        try:
            # New strict JSON aggregation
            final_payload = await self.judge.adjudication(message, votes, session_id, turn_count)
            
            # Store in session state
            session_state.final_callback_payload = final_payload
            
            # Update session state with values from the payload for compatibility
            session_state.is_scam_detected = final_payload.get("scamDetected", False)
            session_state.scam_confidence = 1.0 if session_state.is_scam_detected else 0.0 # Confidence not in strict payload?
            # Actually strict payload doesn't have 'confidence' field in user request!
            # User request: sessionId, scamDetected, totalMessagesExchanged, extractedIntelligence, agentNotes.
            # So session_state.scam_confidence might be undefined/dummy.
            
            # Create a dummy verdict object for compatibility if needed elsewhere
            session_state.council_verdict = CouncilVerdict(
                is_scam=session_state.is_scam_detected,
                confidence=0.99 if session_state.is_scam_detected else 0.0,
                scam_type="aggregated",
                reasoning=final_payload.get("agentNotes", ""),
                votes=votes,
                scam_votes=sum(1 for v in votes if v.is_scam),
                voter_count=len(votes)
            )
            
            logger.info(f"👨‍⚖️ Council Verdict: SCAM={session_state.is_scam_detected}")

        except Exception as e:
            logger.error(f"Judge error: {e}")
            # Fallback verdict in case of judge failure
            session_state.council_verdict = CouncilVerdict(
                is_scam=False,
                confidence=0.0,
                scam_type="error",
                reasoning=f"Judge adjudication failed: {str(e)}",
                votes=votes,
                scam_votes=sum(1 for v in votes if v.is_scam),
                voter_count=len(votes)
            )
            session_state.is_scam_detected = False
            session_state.scam_confidence = 0.0
            session_state.final_callback_payload = {
                "sessionId": session_id,
                "scamDetected": False,
                "totalMessagesExchanged": turn_count,
                "extractedIntelligence": "Judge adjudication failed.",
                "agentNotes": f"Judge adjudication failed: {str(e)}"
            }

        total_elapsed = time.time() - start_time
        logger.info(
            f"Council complete: scam={session_state.council_verdict.is_scam}, conf={session_state.council_verdict.confidence:.2f}, "
            f"type={session_state.council_verdict.scam_type}, votes={session_state.council_verdict.scam_votes}/{session_state.council_verdict.voter_count}, "
            f"total_time={total_elapsed:.2f}s"
        )

        return session_state.council_verdict
