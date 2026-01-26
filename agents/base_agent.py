"""
Base class for Detection Council agents.
All council members inherit from this abstract base class.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from models.schemas import Message, CouncilVote


class BaseDetectionAgent(ABC):
    """
    Abstract base class for all Detection Council agents.
    Each agent must implement the analyze method to provide their vote.
    """
    
    def __init__(self, name: str, agent_type: str):
        """
        Initialize the detection agent.
        
        Args:
            name: Human-readable name of the agent
            agent_type: Category of the agent (Rule/ML/Transformer/LLM/etc)
        """
        self.name = name
        self.agent_type = agent_type
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize any resources needed by the agent.
        Called once before first use.
        """
        pass
    
    @abstractmethod
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVote:
        """
        Analyze a message and return a vote.
        
        Args:
            message: The text message to analyze
            conversation_history: Previous messages in the conversation
            metadata: Additional context (channel, language, locale)
            
        Returns:
            CouncilVote with the agent's decision and reasoning
        """
        pass
    
    def create_vote(
        self,
        is_scam: bool,
        confidence: float,
        reasoning: str,
        features: Optional[List[str]] = None
    ) -> CouncilVote:
        """
        Helper method to create a standardized vote.
        
        Args:
            is_scam: Whether this agent detects scam intent
            confidence: Confidence score between 0 and 1
            reasoning: Explanation for the decision
            features: Key features that influenced the decision
            
        Returns:
            CouncilVote object
        """
        return CouncilVote(
            agent_name=self.name,
            agent_type=self.agent_type,
            is_scam=is_scam,
            confidence=min(max(confidence, 0.0), 1.0),  # Clamp to [0, 1]
            reasoning=reasoning,
            features=features or []
        )
    
    async def cleanup(self) -> None:
        """
        Cleanup resources when the agent is no longer needed.
        Override in subclasses if needed.
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', type='{self.agent_type}')"
