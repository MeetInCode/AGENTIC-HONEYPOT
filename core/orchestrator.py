"""
Honeypot Orchestrator
Main orchestration logic that ties together detection, engagement, and extraction.
"""

from typing import Optional
from datetime import datetime
from rich.console import Console

from models.schemas import (
    HoneypotRequest, 
    HoneypotResponse, 
    Message, 
    ExtractedIntelligence,
    EngagementMetrics,
    SenderType
)
from agents.detection_council import DetectionCouncil
from engagement.engagement_graph import EngagementGraph
from services.intelligence_extractor import IntelligenceExtractor
from services.session_manager import get_session_manager, SessionManager
from services.callback_service import get_callback_service, CallbackService
from config.settings import get_settings


console = Console()


class HoneypotOrchestrator:
    """
    Main orchestrator for the Agentic Honeypot system.
    Coordinates detection, engagement, and intelligence extraction.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.detection_council = DetectionCouncil()
        self.engagement_graph = EngagementGraph()
        self.intelligence_extractor = IntelligenceExtractor()
        self.session_manager: SessionManager = get_session_manager()
        self.callback_service: CallbackService = get_callback_service()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all components."""
        if self._initialized:
            return
        
        console.print("\n[bold cyan]🍯 Initializing Agentic Honeypot System...[/bold cyan]")
        
        await self.detection_council.initialize()
        await self.engagement_graph.initialize()
        await self.intelligence_extractor.initialize()
        
        self._initialized = True
        console.print("[bold green]✅ Honeypot System Ready![/bold green]\n")
    
    async def process_message(self, request: HoneypotRequest) -> HoneypotResponse:
        """
        Process an incoming message through the honeypot pipeline.
        
        Flow:
        1. Get/create session
        2. Run Detection Council
        3. If scam detected, engage with LangGraph agent
        4. Extract intelligence
        5. Update session and potentially send callback
        
        Args:
            request: The incoming message request
            
        Returns:
            HoneypotResponse with results
        """
        if not self._initialized:
            await self.initialize()
        
        session_id = request.sessionId
        console.print(f"\n[bold yellow]📨 Processing message for session: {session_id}[/bold yellow]")
        
        # Get or create session
        session = self.session_manager.get_or_create_session(session_id)
        
        # Add incoming message to history
        incoming_message = Message(
            sender=SenderType.SCAMMER,
            text=request.message.text,
            timestamp=request.message.timestamp
        )
        
        # Convert conversation history from request
        history = request.conversationHistory or []
        
        # Update session with new message
        self.session_manager.update_session(
            session_id=session_id,
            message=incoming_message
        )
        
        # Prepare metadata
        metadata = None
        if request.metadata:
            metadata = {
                "channel": request.metadata.channel.value if request.metadata.channel else "SMS",
                "language": request.metadata.language or "English",
                "locale": request.metadata.locale or "IN"
            }
        
        # Step 1: Run Detection Council (always analyze, even if previously detected)
        verdict = await self.detection_council.analyze(
            message=request.message.text,
            conversation_history=history,
            metadata=metadata
        )
        
        # Update session with verdict
        self.session_manager.update_session(
            session_id=session_id,
            is_scam=verdict.is_scam,
            verdict=verdict
        )
        
        # Step 2: Extract intelligence from current message
        new_intel = await self.intelligence_extractor.extract(
            message=request.message.text,
            conversation_history=history
        )
        
        self.session_manager.update_session(
            session_id=session_id,
            intelligence=new_intel
        )
        
        # Get updated session
        session = self.session_manager.get_session(session_id)
        
        # Step 3: If scam detected, engage with agent
        agent_response = None
        if verdict.is_scam:
            console.print("[bold red]🚨 Scam detected! Activating engagement agent...[/bold red]")
            
            # Determine scam type from verdict
            scam_type = self._determine_scam_type(verdict)
            
            # Generate engagement response
            engagement_result = await self.engagement_graph.engage(
                session_id=session_id,
                scammer_message=request.message.text,
                conversation_history=history,
                scam_type=scam_type,
                existing_intel=session.extracted_intelligence
            )
            
            agent_response = engagement_result.get("response", "")
            
            # Update agent notes
            self.session_manager.update_session(
                session_id=session_id,
                agent_note=f"Goal: {engagement_result.get('engagement_goal', 'unknown')}"
            )
            
            console.print(f"[bold green]💬 Agent response:[/bold green] {agent_response}")
        
        # Get final session state
        session = self.session_manager.get_session(session_id)
        
        # Step 4: Check if we should send callback
        should_callback = await self._should_send_callback(session, verdict.is_scam)
        
        if should_callback:
            await self._send_callback(session)
        
        # Build response
        response = HoneypotResponse(
            status="success",
            scamDetected=verdict.is_scam,
            agentResponse=agent_response,
            engagementMetrics=EngagementMetrics(
                engagementDurationSeconds=session.get_duration_seconds(),
                totalMessagesExchanged=session.total_messages
            ),
            extractedIntelligence=session.extracted_intelligence,
            agentNotes=self._generate_agent_notes(session, verdict),
            councilVerdict=verdict
        )
        
        return response
    
    def _determine_scam_type(self, verdict) -> str:
        """Determine scam type from verdict features."""
        # Collect all features from votes
        all_features = []
        for vote in verdict.votes:
            if vote.features:
                all_features.extend(vote.features)
        
        features_text = " ".join(all_features).lower()
        
        if "upi" in features_text or "payment" in features_text:
            return "upi_fraud"
        elif "bank" in features_text or "account" in features_text:
            return "bank_fraud"
        elif "lottery" in features_text or "prize" in features_text or "won" in features_text:
            return "lottery_scam"
        elif "kyc" in features_text or "aadhar" in features_text:
            return "kyc_scam"
        elif "sbi" in features_text or "rbi" in features_text or "icici" in features_text:
            return "impersonation"
        else:
            return "phishing"
    
    def _generate_agent_notes(self, session, verdict) -> str:
        """Generate comprehensive agent notes for the response."""
        notes_parts = []
        
        # Scam type and confidence
        if verdict.is_scam:
            notes_parts.append(f"Scam confirmed with {verdict.confidence:.0%} confidence.")
        else:
            notes_parts.append("No scam detected.")
        
        # Session notes
        if session.agent_notes:
            notes_parts.append(session.agent_notes)
        
        # Intelligence summary
        intel = session.extracted_intelligence
        if not intel.is_empty():
            intel_summary = []
            if intel.upiIds:
                intel_summary.append(f"UPI: {len(intel.upiIds)}")
            if intel.phoneNumbers:
                intel_summary.append(f"Phones: {len(intel.phoneNumbers)}")
            if intel.phishingLinks:
                intel_summary.append(f"Links: {len(intel.phishingLinks)}")
            if intel_summary:
                notes_parts.append(f"Intel gathered: {', '.join(intel_summary)}")
        
        return " | ".join(notes_parts)
    
    async def _should_send_callback(self, session, is_scam: bool) -> bool:
        """
        Determine if we should send the final callback.
        
        Conditions:
        - Scam was detected
        - Either sufficient intel gathered OR max turns reached
        - Callback not already sent
        """
        if session.callback_sent:
            return False
        
        if not is_scam:
            return False
        
        # Check if we have meaningful intelligence
        intel = session.extracted_intelligence
        has_intel = (
            len(intel.upiIds) > 0 or
            len(intel.phoneNumbers) > 0 or
            len(intel.phishingLinks) > 0 or
            len(intel.bankAccounts) > 0
        )
        
        # Check turn count
        max_turns = self.settings.max_conversation_turns
        high_turn_count = session.total_messages >= max_turns
        
        # Send callback if we have intel OR reached max turns
        return has_intel or high_turn_count
    
    async def _send_callback(self, session) -> None:
        """Send the final callback to GUVI."""
        try:
            success = await self.callback_service.send_final_result(
                session_id=session.session_id,
                scam_detected=session.is_scam_detected,
                total_messages=session.total_messages,
                intelligence=session.extracted_intelligence,
                agent_notes=session.agent_notes or "Engagement completed."
            )
            
            if success:
                self.session_manager.update_session(
                    session_id=session.session_id,
                    callback_sent=True
                )
        except Exception as e:
            console.print(f"[bold red]❌ Callback failed: {e}[/bold red]")
    
    async def force_callback(self, session_id: str) -> bool:
        """
        Force sending callback for a session.
        Used for manual triggering or testing.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            return False
        
        await self._send_callback(session)
        return True
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.detection_council.cleanup()
        await self.callback_service.close()
        console.print("[dim]🧹 Honeypot system cleaned up[/dim]")


# Singleton instance
_orchestrator: Optional[HoneypotOrchestrator] = None


async def get_orchestrator() -> HoneypotOrchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = HoneypotOrchestrator()
        await _orchestrator.initialize()
    return _orchestrator
