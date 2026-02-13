"""
Data Schemas for Agentic Honeypot.
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# ─── 1. API Request/Response ──────────────────────────────────────

class Message(BaseModel):
    sender: str
    text: str
    timestamp: Union[str, int, float]

class Metadata(BaseModel):
    channel: Optional[str] = "SMS"
    language: Optional[str] = "English"
    locale: Optional[str] = "IN"

class HoneypotRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[dict] = []
    metadata: Optional[Metadata] = None

class HoneypotResponse(BaseModel):
    sessionId: str
    status: str = Field(default="success")
    reply: Optional[str] = None
    scamDetected: bool
    confidence: float

# ─── 2. Internal State ────────────────────────────────────────────

class ExtractedIntelligence(BaseModel):
    bankAccounts: List[str] = Field(default_factory=list)
    upiIds: List[str] = Field(default_factory=list)
    phishingLinks: List[str] = Field(default_factory=list)
    phoneNumbers: List[str] = Field(default_factory=list)
    suspiciousKeywords: List[str] = Field(default_factory=list)

class AgentOutput(BaseModel):
    """Strict JSON output format for all council agents."""
    sessionId: str
    scamDetected: bool
    totalMessagesExchanged: Optional[int] = 0
    extractedIntelligence: ExtractedIntelligence
    agentNotes: str

class CouncilVote(BaseModel):
    """Internal representation of a single agent's vote."""
    agent_name: str
    is_scam: bool
    confidence: float
    reasoning: str
    scam_type: Optional[str] = "unknown"
    extracted_intelligence: Dict[str, Any] = Field(default_factory=dict)

class CouncilVerdict(BaseModel):
    """Aggregated verdict from the council."""
    is_scam: bool
    confidence: float
    scam_type: str
    scam_votes: int
    voter_count: int
    reasoning: str
    votes: List[CouncilVote]

class SessionState(BaseModel):
    session_id: str
    messages: List[dict] = Field(default_factory=list)
    turn_count: int = 0
    created_at: Any = None
    last_activity: Any = None
    is_scam_detected: bool = False
    scam_confidence: float = 0.0
    scam_type: str = "unknown"
    extracted_intelligence: Dict[str, Any] = Field(default_factory=dict)
    persona_id: str = "default"
    agent_responses: List[str] = Field(default_factory=list)
    callback_sent: bool = False
    callback_response: Optional[str] = None
    council_verdict: Optional[CouncilVerdict] = None
    council_votes: List[CouncilVote] = Field(default_factory=list)
    # Judge-composed callback payload (used by callback service)
    final_callback_payload: Optional[Dict[str, Any]] = None

# ─── 3. Callback ──────────────────────────────────────────────────

class EngagementMetrics(BaseModel):
    totalMessagesExchanged: int
    engagementDurationSeconds: float
    scammerResponseRate: float = 0.0
    longestScammerMessage: int = 0

class CallbackPayload(BaseModel):
    sessionId: str
    scamDetected: bool
    totalMessagesExchanged: int
    extractedIntelligence: ExtractedIntelligence
    agentNotes: str
