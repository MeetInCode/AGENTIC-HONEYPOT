"""
🧰 MetaModerator Agent
Ensemble voter and meta-agent for final verdict determination.
Aggregates votes from all council members and provides justification.
"""

from typing import List, Optional, Dict
from collections import Counter

from .base_agent import BaseDetectionAgent
from models.schemas import Message, CouncilVote, CouncilVerdict
from config.settings import get_settings


class MetaModeratorAgent(BaseDetectionAgent):
    """
    Meta-agent that aggregates votes from all council members
    and produces a final verdict with justification.
    Uses weighted voting and consensus analysis.
    """
    
    def __init__(self):
        super().__init__(
            name="🧰 MetaModerator",
            agent_type="Meta-Agent (Ensemble)"
        )
        self.settings = get_settings()
        
        # Agent weights for voting (higher = more influence)
        self.agent_weights: Dict[str, float] = {
            "🕵️‍♂️ RuleGuard": 1.0,        # Good for pattern matching
            "🧮 FastML": 1.2,              # Trained on data
            "🤖 BertLite": 1.3,            # Deep semantic understanding
            "📜 LexJudge": 1.5,            # LLM reasoning
            "🔍 OutlierSentinel": 0.8,     # Anomaly detection
            "🧵 ContextSeer": 1.4,         # Context analysis
            "🌪️ MistralLarge": 1.5,        # Strategic analysis
            "🤖 DeepSeek": 1.4,            # DeepSeek classification
            "🤖 GPT-120B": 1.6,            # General intelligence (GPT-120B)
        }
        
        # Minimum votes required to declare scam
        self.min_votes_for_scam = 3
        
        # Confidence threshold for high-confidence decisions
        self.high_confidence_threshold = 0.7
    
    async def initialize(self) -> None:
        """Initialize the meta-moderator."""
        self._initialized = True
    
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVote:
        """
        This method is not used for MetaModerator.
        Use aggregate_votes instead.
        """
        return self.create_vote(
            is_scam=False,
            confidence=0.5,
            reasoning="MetaModerator requires aggregate_votes method.",
            features=[]
        )
    
    async def aggregate_votes(self, votes: List[CouncilVote]) -> CouncilVerdict:
        """
        Aggregate all council votes into a final verdict.
        
        Args:
            votes: List of votes from all council members
            
        Returns:
            CouncilVerdict with final decision and justification
        """
        if not votes:
            return self._create_default_verdict()
        
        # Calculate weighted votes
        weighted_scam_votes = 0.0
        weighted_not_scam_votes = 0.0
        total_weight = 0.0
        
        scam_voters = []
        not_scam_voters = []
        
        for vote in votes:
            weight = self.agent_weights.get(vote.agent_name, 1.0)
            adjusted_weight = weight * vote.confidence
            total_weight += weight
            
            if vote.is_scam:
                weighted_scam_votes += adjusted_weight
                scam_voters.append(vote)
            else:
                weighted_not_scam_votes += adjusted_weight
                not_scam_voters.append(vote)
        
        # Calculate aggregate confidence
        if total_weight > 0:
            scam_confidence = weighted_scam_votes / total_weight
        else:
            scam_confidence = 0.5
        
        # Simple majority voting as a baseline
        simple_scam_votes = len(scam_voters)
        simple_total = len(votes)
        
        # Decision logic
        is_scam = False
        
        # Condition 1: Weighted confidence above threshold
        if scam_confidence >= self.settings.scam_confidence_threshold:
            is_scam = True
        
        # Condition 2: Majority of agents detected scam
        if simple_scam_votes >= (simple_total / 2):
            is_scam = True
        
        # Condition 3: High-confidence agreement from key agents
        high_confidence_scam = [
            v for v in scam_voters 
            if v.confidence >= self.high_confidence_threshold
        ]
        if len(high_confidence_scam) >= self.min_votes_for_scam:
            is_scam = True
        
        # Override: If LexJudge (LLM) is very confident, weight heavily
        for vote in votes:
            if vote.agent_name == "📜 LexJudge" and vote.confidence >= 0.85:
                is_scam = vote.is_scam
                scam_confidence = vote.confidence
        
        # Generate vote breakdown
        vote_breakdown = self._generate_vote_breakdown(votes)
        
        # Generate justification
        justification = self._generate_justification(
            is_scam=is_scam,
            votes=votes,
            scam_voters=scam_voters,
            not_scam_voters=not_scam_voters,
            scam_confidence=scam_confidence
        )
        
        return CouncilVerdict(
            is_scam=is_scam,
            confidence=scam_confidence if is_scam else (1 - scam_confidence),
            votes=votes,
            justification=justification,
            vote_breakdown=vote_breakdown
        )
    
    def _generate_vote_breakdown(self, votes: List[CouncilVote]) -> str:
        """Generate a summary of voting results."""
        scam_count = sum(1 for v in votes if v.is_scam)
        total = len(votes)
        
        lines = [f"Total: {scam_count}/{total} detected scam"]
        
        for vote in votes:
            emoji = "🚨" if vote.is_scam else "✅"
            lines.append(
                f"  {emoji} {vote.agent_name}: "
                f"{'SCAM' if vote.is_scam else 'SAFE'} "
                f"({vote.confidence:.0%})"
            )
        
        return "\n".join(lines)
    
    def _generate_justification(
        self,
        is_scam: bool,
        votes: List[CouncilVote],
        scam_voters: List[CouncilVote],
        not_scam_voters: List[CouncilVote],
        scam_confidence: float
    ) -> str:
        """Generate a detailed justification for the verdict."""
        if is_scam:
            # Collect all features from scam voters
            all_features = []
            for voter in scam_voters:
                if voter.features:
                    all_features.extend(voter.features[:3])
            
            unique_features = list(set(all_features))[:5]
            
            justification = (
                f"SCAM DETECTED with {scam_confidence:.0%} aggregate confidence. "
                f"{len(scam_voters)}/{len(votes)} council members flagged this message. "
            )
            
            if unique_features:
                justification += f"Key indicators: {', '.join(unique_features)}. "
            
            # Add top reasoning
            if scam_voters:
                top_voter = max(scam_voters, key=lambda v: v.confidence)
                justification += f"Primary assessment: {top_voter.reasoning[:200]}"
            
        else:
            justification = (
                f"Message deemed SAFE with {1-scam_confidence:.0%} confidence. "
                f"Only {len(scam_voters)}/{len(votes)} agents detected potential issues. "
            )
            
            if not_scam_voters:
                top_voter = max(not_scam_voters, key=lambda v: v.confidence)
                justification += f"Assessment: {top_voter.reasoning[:200]}"
        
        return justification
    
    def _create_default_verdict(self) -> CouncilVerdict:
        """Create a default verdict when no votes are available."""
        return CouncilVerdict(
            is_scam=False,
            confidence=0.5,
            votes=[],
            justification="No council votes received. Defaulting to safe.",
            vote_breakdown="No votes available"
        )
