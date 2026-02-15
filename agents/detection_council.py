"""
Detection Council — orchestrates the 5 LLM council members.

Council Members:
1. LlamaScoutVoter (Groq) - CM1
2. GptOssVoter     (Groq) - CM2
3. NemotronVoter   (NVIDIA) - CM3
4. MinimaxVoter    (NVIDIA) - CM4
5. LlamaScoutVoter (Groq) - CM5 (Second Scout, as requested)
"""

import asyncio
import logging
import time
from typing import List, Tuple

from models.schemas import CouncilVote, CouncilVerdict
from agents.nvidia_agents import MinimaxVoter, NemotronVoter
from agents.groq_agents import (
    GptOssVoter,
    LlamaScoutVoter,
)
from utils.rich_printer import print_council_votes

logger = logging.getLogger(__name__)


class DetectionCouncil:
    """Runs the 5 detection voters in parallel and returns their votes + a lightweight verdict."""

    def __init__(self):
        # Initialize voters based on configuration
        from config.settings import get_settings
        settings = get_settings()
        
        self.voters = []
        
        # Helper to add voters
        def add_voters(voter_class, count):
            for _ in range(count):
                self.voters.append(voter_class())
        
        add_voters(LlamaScoutVoter, settings.council_scout_count)
        add_voters(GptOssVoter, settings.council_gpt_oss_count)
        add_voters(NemotronVoter, settings.council_nemotron_count)
        add_voters(MinimaxVoter, settings.council_minimax_count)
        
        # New Voters
        from agents.groq_agents import GroqCompoundVoter, QwenVoter
        add_voters(GroqCompoundVoter, settings.council_compound_count)
        add_voters(QwenVoter, settings.council_qwen_count)

        # Optional voters (default 0)
        from agents.groq_agents import ContextualVoter, LlamaPromptGuardVoter
        add_voters(ContextualVoter, settings.council_contextual_count)
        add_voters(LlamaPromptGuardVoter, settings.council_prompt_guard_count)

        logger.info(f"Detection Council initialized with {len(self.voters)} voters: "
                    f"Scout={settings.council_scout_count}, GPT-OSS={settings.council_gpt_oss_count}, "
                    f"Nemotron={settings.council_nemotron_count}, Minimax={settings.council_minimax_count}, "
                    f"Contextual={settings.council_contextual_count}, Guard={settings.council_prompt_guard_count}")

    async def analyze(
        self,
        message: str,
        context: str = "No prior context",
        session_id: str = "unknown",
        turn_count: int = 0,
    ) -> Tuple[List[CouncilVote], CouncilVerdict]:
        """
        Run all voters fully in parallel and return:
          - the raw list of CouncilVote objects (per-agent intelligence)
          - an aggregated CouncilVerdict (simple majority / max-confidence merge)

        No LLM waits on another here — asyncio.gather is used to fan out calls.
        """
        start_time = time.time()

        vote_tasks = [
            voter.vote(message, context, session_id, turn_count) for voter in self.voters
        ]
        results = await asyncio.gather(*vote_tasks, return_exceptions=True)

        votes: List[CouncilVote] = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Voter {self.voters[i].__class__.__name__} failed: {res}")
                # User requested NULL for failed agents, so we skip adding a vote
                continue
            elif res is None:
                logger.warning(f"Voter {self.voters[i].__class__.__name__} returned NULL (skipped)")
                continue
            else:
                votes.append(res)

        voting_elapsed = time.time() - start_time

        # ── Rich Print: Council Votes ──
        print_council_votes(votes, voting_elapsed)

        # Lightweight aggregation for immediate API response
        # Use strict majority (>50%) to avoid false positives
        scam_votes = [v for v in votes if v.is_scam]
        safe_votes = [v for v in votes if not v.is_scam and v.scam_type != "error"]
        
        # Strict detection: require >50% scam votes (not >=) AND at least 2 scam votes
        # This prevents false positives from single-agent errors
        is_scam = len(scam_votes) > len(votes) / 2 and len(scam_votes) >= 2
        
        # If tied or unclear, default to safe (avoid false positives)
        if len(scam_votes) == len(safe_votes):
            is_scam = False
        
        # Calculate confidence: use average of scam votes, but require minimum threshold
        extracted_confidences = [v.confidence for v in votes if v.is_scam]
        if extracted_confidences:
            avg_conf = sum(extracted_confidences) / len(extracted_confidences)
            max_conf = max(extracted_confidences)
            # Use average but cap at max (more conservative)
            confidence = min(avg_conf, max_conf)
        else:
            confidence = 0.0
        
        # Require minimum confidence threshold to avoid false positives
        if is_scam and confidence < 0.5:
            is_scam = False
            confidence = 0.0
        
        scam_type = "unknown"
        if scam_votes:
            # Use most common scam type from scam votes
            scam_types = [v.scam_type for v in scam_votes if v.scam_type != "error"]
            if scam_types:
                scam_type = max(set(scam_types), key=scam_types.count)
            else:
                scam_type = scam_votes[0].scam_type if scam_votes else "unknown"

        verdict = CouncilVerdict(
            is_scam=is_scam,
            confidence=max_conf,
            scam_type=scam_type,
            scam_votes=len(scam_votes),
            voter_count=len(votes),
            reasoning=f"{len(scam_votes)}/{len(votes)} voted scam.",
            votes=votes,
        )

        total_elapsed = time.time() - start_time
        logger.info(
            f"Council complete: scam={verdict.is_scam}, conf={verdict.confidence:.2f}, "
            f"type={verdict.scam_type}, votes={verdict.scam_votes}/{verdict.voter_count}, "
            f"total_time={total_elapsed:.2f}s"
        )

        return votes, verdict
