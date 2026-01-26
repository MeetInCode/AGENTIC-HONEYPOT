"""
Unit tests for Detection Council agents.
"""

import pytest
import asyncio
from typing import List

# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import Message, CouncilVote
from agents.rule_guard import RuleGuardAgent
from agents.fast_ml import FastMLAgent


class TestRuleGuardAgent:
    """Tests for RuleGuard agent."""
    
    @pytest.fixture
    def agent(self):
        return RuleGuardAgent()
    
    @pytest.mark.asyncio
    async def test_initialization(self, agent):
        """Test agent initialization."""
        await agent.initialize()
        assert agent._initialized is True
    
    @pytest.mark.asyncio
    async def test_scam_detection_bank_block(self, agent):
        """Test detection of bank blocking scam."""
        await agent.initialize()
        
        message = "Your bank account will be blocked today. Verify immediately."
        vote = await agent.analyze(message)
        
        assert isinstance(vote, CouncilVote)
        assert vote.is_scam is True
        assert vote.confidence > 0.3
        assert "threat" in vote.reasoning.lower() or "urgency" in vote.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_scam_detection_upi_request(self, agent):
        """Test detection of UPI request scam."""
        await agent.initialize()
        
        message = "Share your UPI PIN to verify your account. Send to verify@upi"
        vote = await agent.analyze(message)
        
        assert vote.is_scam is True
        assert "info_request" in vote.reasoning.lower() or any("upi" in f.lower() for f in vote.features or [])
    
    @pytest.mark.asyncio
    async def test_legitimate_message(self, agent):
        """Test that legitimate messages are not flagged."""
        await agent.initialize()
        
        message = "Hi, how are you doing? Let's meet for coffee tomorrow."
        vote = await agent.analyze(message)
        
        assert vote.is_scam is False or vote.confidence < 0.3


class TestFastMLAgent:
    """Tests for FastML agent."""
    
    @pytest.fixture
    def agent(self):
        return FastMLAgent()
    
    @pytest.mark.asyncio
    async def test_initialization(self, agent):
        """Test agent initialization and fallback model training."""
        await agent.initialize()
        assert agent._initialized is True
        assert agent.pipeline is not None
    
    @pytest.mark.asyncio
    async def test_scam_classification(self, agent):
        """Test scam classification."""
        await agent.initialize()
        
        message = "URGENT: Your account suspended. Click link to verify OTP."
        vote = await agent.analyze(message)
        
        assert isinstance(vote, CouncilVote)
        assert vote.agent_name == "🧮 FastML"
        assert vote.is_scam is True
    
    @pytest.mark.asyncio
    async def test_legitimate_classification(self, agent):
        """Test legitimate message classification."""
        await agent.initialize()
        
        message = "Thank you for attending the meeting. Please review the attached document."
        vote = await agent.analyze(message)
        
        # Should be classified as not scam or low confidence
        assert vote.is_scam is False or vote.confidence < 0.5


# Detection Council integration test
class TestDetectionCouncil:
    """Integration tests for Detection Council."""
    
    @pytest.mark.asyncio
    async def test_council_initialization(self):
        """Test council initialization."""
        from agents.detection_council import DetectionCouncil
        
        council = DetectionCouncil()
        await council.initialize()
        
        assert council._initialized is True
        assert len(council.agents) == 6
    
    @pytest.mark.asyncio
    async def test_council_analysis(self):
        """Test full council analysis."""
        from agents.detection_council import DetectionCouncil
        
        council = DetectionCouncil()
        await council.initialize()
        
        message = "Your SBI account blocked. Share OTP now to unblock."
        verdict = await council.analyze(message)
        
        assert verdict is not None
        assert hasattr(verdict, 'is_scam')
        assert hasattr(verdict, 'confidence')
        assert len(verdict.votes) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
