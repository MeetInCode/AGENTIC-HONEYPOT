"""
Pydantic schemas for API requests and responses.
Based on the GUVI API specification from the problem statement.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class SenderType(str, Enum):
    """Message sender type enumeration."""
    SCAMMER = "scammer"
    USER = "user"


class ChannelType(str, Enum):
    """Communication channel type."""
    SMS = "SMS"
    WHATSAPP = "WhatsApp"
    EMAIL = "Email"
    CHAT = "Chat"


# ==========================================
# REQUEST MODELS
# ==========================================

class Message(BaseModel):
    """Represents a single message in the conversation."""
    sender: str = "scammer"
    text: str
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        populate_by_name = True
        extra = 'ignore'


class Metadata(BaseModel):
    """Optional metadata about the conversation context."""
    channel: Optional[str] = "SMS"
    language: Optional[str] = "English"
    locale: Optional[str] = "IN"

    class Config:
        populate_by_name = True
        extra = 'ignore'


class HoneypotRequest(BaseModel):
    """
    API request model for incoming messages.
    """
    sessionId: str = Field(..., alias="session_id")
    message: Message = Field(..., alias="msg")
    conversationHistory: List[Message] = Field(
        default_factory=list,
        alias="history"
    )
    metadata: Optional[Metadata] = Field(
        default_factory=Metadata,
        description="Optional context metadata"
    )

    class Config:
        populate_by_name = True
        extra = 'ignore'


# ==========================================
# RESPONSE MODELS
# ==========================================

class ExtractedIntelligence(BaseModel):
    """Intelligence extracted from scammer interactions."""
    bankAccounts: List[str] = Field(default_factory=list)
    upiIds: List[str] = Field(default_factory=list)
    phishingLinks: List[str] = Field(default_factory=list)
    phoneNumbers: List[str] = Field(default_factory=list)
    suspiciousKeywords: List[str] = Field(default_factory=list)
    emailAddresses: List[str] = Field(default_factory=list)
    
    def merge(self, other: "ExtractedIntelligence") -> "ExtractedIntelligence":
        """Merge two intelligence objects, removing duplicates."""
        return ExtractedIntelligence(
            bankAccounts=list(set(self.bankAccounts + other.bankAccounts)),
            upiIds=list(set(self.upiIds + other.upiIds)),
            phishingLinks=list(set(self.phishingLinks + other.phishingLinks)),
            phoneNumbers=list(set(self.phoneNumbers + other.phoneNumbers)),
            suspiciousKeywords=list(set(self.suspiciousKeywords + other.suspiciousKeywords)),
            emailAddresses=list(set(self.emailAddresses + other.emailAddresses)),
        )
    
    def is_empty(self) -> bool:
        """Check if no intelligence has been extracted."""
        return not any([
            self.bankAccounts,
            self.upiIds,
            self.phishingLinks,
            self.phoneNumbers,
            self.suspiciousKeywords,
            self.emailAddresses,
        ])


class EngagementMetrics(BaseModel):
    """Metrics about the engagement with the scammer."""
    engagementDurationSeconds: int = 0
    totalMessagesExchanged: int = 0


class HoneypotResponse(BaseModel):
    """
    API response model matching GUVI specification.
    """
    status: Literal["success", "error"] = "success"
    scamDetected: bool = False
    agentResponse: Optional[str] = Field(
        default=None,
        description="Agent's response to continue the conversation"
    )
    engagementMetrics: EngagementMetrics = Field(default_factory=EngagementMetrics)
    extractedIntelligence: ExtractedIntelligence = Field(
        default_factory=ExtractedIntelligence
    )
    agentNotes: Optional[str] = None
    councilVerdict: Optional["CouncilVerdict"] = None
    error: Optional[str] = None


# ==========================================
# DETECTION COUNCIL MODELS
# ==========================================

class CouncilVote(BaseModel):
    """Vote from a single detection council member."""
    agent_name: str = Field(..., description="Name of the council agent")
    agent_type: str = Field(..., description="Type of the agent (Rule/ML/LLM/etc)")
    is_scam: bool = Field(..., description="Whether the agent detects scam")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    reasoning: str = Field(..., description="Explanation for the decision")
    features: Optional[List[str]] = Field(
        default=None,
        description="Key features that influenced the decision"
    )


class CouncilVerdict(BaseModel):
    """Final verdict from the Detection Council."""
    is_scam: bool = Field(..., description="Final decision")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Aggregate confidence")
    votes: List[CouncilVote] = Field(default_factory=list)
    justification: str = Field(..., description="Meta-moderator's justification")
    vote_breakdown: str = Field(..., description="Summary of voting")


# ==========================================
# SESSION STATE MODELS
# ==========================================

class SessionState(BaseModel):
    """State maintained for an active session."""
    session_id: str
    is_scam_detected: bool = False
    total_messages: int = 0
    start_time: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    extracted_intelligence: ExtractedIntelligence = Field(
        default_factory=ExtractedIntelligence
    )
    conversation_history: List[Message] = Field(default_factory=list)
    engagement_goals: List[str] = Field(default_factory=list)
    council_verdict: Optional[CouncilVerdict] = None
    agent_notes: str = ""
    callback_sent: bool = False
    
    def get_duration_seconds(self) -> int:
        """Calculate engagement duration in seconds."""
        return int((self.last_activity - self.start_time).total_seconds())


# ==========================================
# CALLBACK MODELS
# ==========================================

class CallbackPayload(BaseModel):
    """
    Payload for the mandatory GUVI callback.
    POST to https://hackathon.guvi.in/api/updateHoneyPotFinalResult
    """
    sessionId: str
    scamDetected: bool
    totalMessagesExchanged: int
    extractedIntelligence: dict  # Serialized ExtractedIntelligence
    agentNotes: str


# Update forward references
HoneypotResponse.model_rebuild()
