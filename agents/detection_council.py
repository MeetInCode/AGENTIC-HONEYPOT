"""
Detection Council — orchestrates the 5 LLM council members.

Each council member is a fully independent agent:
  1. NemotronVoter            (NVIDIA safety / bank fraud)
  2. MultilingualSafetyVoter  (NVIDIA multilingual safety)
  3. MinimaxVoter             (NVIDIA linguistic patterns)
  4. LlamaScoutVoter          (Groq realism / anomaly)
  5. GptOssVoter              (Groq scam-playbook strategy)

All 5 run in parallel for every message. None of them wait on each other.
Only the Judge LLM (separate agent) aggregates their outputs at callback time.
"""

import asyncio
import logging
import time
from typing import List, Tuple

from models.schemas import CouncilVote, CouncilVerdict
from agents.nvidia_agents import NemotronVoter, MultilingualSafetyVoter, MinimaxVoter
from agents.groq_agents import LlamaScoutVoter, GptOssVoter
from utils.rich_printer import print_council_votes

logger = logging.getLogger(__name__)


class DetectionCouncil:
    """Runs the 5 detection voters in parallel and returns their votes + a lightweight verdict."""

    def __init__(self):
        # Initialize all voters (independent agents)
        self.voters = [
            NemotronVoter(),
            MultilingualSafetyVoter(),
            MinimaxVoter(),
            LlamaScoutVoter(),
            GptOssVoter(),
        ]
        logger.info(f"Detection Council initialized with {len(self.voters)} voters")

    async def analyze(
        self,
        message: str,
        context: str = "No prior context",
        session_id: str = "unknown",
        turn_count: int = 0,
    ) -> Tuple[List[CouncilVote], CouncilVerdict]:
        """
        Run all 5 voters fully in parallel and return:
          - the raw list of CouncilVote objects (per-agent intelligence)
          - an aggregated CouncilVerdict (simple majority / max-confidence merge)

        No LLM waits on another here — asyncio.gather is used to fan out calls.
        """
        start_time = time.time()

        # Fan out to all council members concurrently
        vote_tasks = [
            voter.vote(message, context, session_id, turn_count) for voter in self.voters
        ]
        results = await asyncio.gather(*vote_tasks, return_exceptions=True)

        votes: List[CouncilVote] = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Voter {self.voters[i].__class__.__name__} failed: {res}")
                votes.append(
                    CouncilVote(
                        agent_name=self.voters[i].__class__.__name__,
                        is_scam=False,
                        confidence=0.0,
                        reasoning=f"Voter error: {str(res)[:100]}",
                        scam_type="error",
                        extracted_intelligence={},
                    )
                )
            else:
                votes.append(res)

        voting_elapsed = time.time() - start_time

        # ── Rich Print: Council Votes ──
        print_council_votes(votes, voting_elapsed)

        # Lightweight, non-LLM aggregation for quick state updates
        scam_votes = [v for v in votes if v.is_scam]
        is_scam = len(scam_votes) > 0
        voter_count = len(votes)
        max_conf = max((v.confidence for v in votes), default=0.0)
        scam_type = scam_votes[0].scam_type if scam_votes else "unknown"
        reasoning = (
            f"{len(scam_votes)}/{voter_count} council members flagged this as scam."
            if voter_count > 0
            else "No council votes available."
        )

        verdict = CouncilVerdict(
            is_scam=is_scam,
            confidence=max_conf,
            scam_type=scam_type,
            scam_votes=len(scam_votes),
            voter_count=voter_count,
            reasoning=reasoning,
            votes=votes,
        )

        total_elapsed = time.time() - start_time
        logger.info(
            f"Council complete: scam={verdict.is_scam}, conf={verdict.confidence:.2f}, "
            f"type={verdict.scam_type}, votes={verdict.scam_votes}/{verdict.voter_count}, "
            f"total_time={total_elapsed:.2f}s"
        )

        return votes, verdict

