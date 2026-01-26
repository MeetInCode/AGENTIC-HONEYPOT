"""
Engagement Graph using LangGraph.
Manages conversation state and transitions for scammer engagement.
"""

from typing import Annotated, TypedDict, List, Optional, Literal
from datetime import datetime
import asyncio

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage

from .persona_manager import PersonaManager, VictimPersona
from .response_generator import ResponseGenerator
from models.schemas import Message, ExtractedIntelligence, SenderType
from config.settings import get_settings


class EngagementState(TypedDict):
    """State maintained throughout the engagement."""
    messages: Annotated[list, add_messages]
    session_id: str
    persona_id: str
    persona: Optional[dict]
    turn_count: int
    engagement_goal: str
    extracted_intelligence: dict
    should_continue: bool
    last_response: str
    scam_type: str
    engagement_notes: List[str]


class EngagementGraph:
    """
    LangGraph-based engagement workflow for scammer interaction.
    
    States:
    1. analyze_intent - Understand scammer's current message
    2. select_goal - Choose engagement goal based on context
    3. generate_response - Create persona-appropriate response
    4. extract_intel - Extract any revealed intelligence
    5. decide_continue - Determine if engagement should continue
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.persona_manager = PersonaManager()
        self.response_generator = ResponseGenerator()
        self.graph = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the engagement graph."""
        if self._initialized:
            return
        
        await self.response_generator.initialize()
        self._build_graph()
        self._initialized = True
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow."""
        builder = StateGraph(EngagementState)
        
        # Add nodes
        builder.add_node("analyze_intent", self._analyze_intent)
        builder.add_node("select_goal", self._select_goal)
        builder.add_node("generate_response", self._generate_response)
        builder.add_node("extract_intel", self._extract_intel)
        builder.add_node("decide_continue", self._decide_continue)
        
        # Add edges
        builder.add_edge(START, "analyze_intent")
        builder.add_edge("analyze_intent", "select_goal")
        builder.add_edge("select_goal", "generate_response")
        builder.add_edge("generate_response", "extract_intel")
        builder.add_edge("extract_intel", "decide_continue")
        
        # Conditional edge for continuation
        builder.add_conditional_edges(
            "decide_continue",
            self._should_end,
            {
                "continue": END,  # Return response and wait for next message
                "end": END,       # End the engagement
            }
        )
        
        self.graph = builder.compile()
    
    async def _analyze_intent(self, state: EngagementState) -> dict:
        """Analyze the scammer's intent from their message."""
        # Get the latest scammer message
        messages = state.get("messages", [])
        if not messages:
            return {"engagement_notes": ["No message to analyze"]}
        
        latest_msg = messages[-1]
        if isinstance(latest_msg, HumanMessage):
            content = latest_msg.content
        else:
            content = str(latest_msg)
        
        # Simple intent classification
        intent_keywords = {
            "requesting_otp": ["otp", "code", "verification"],
            "requesting_upi": ["upi", "pay", "send", "transfer"],
            "requesting_bank": ["account", "ifsc", "bank", "number"],
            "threatening": ["blocked", "suspended", "urgent", "immediately"],
            "offering_reward": ["won", "prize", "reward", "cashback", "lottery"],
            "building_trust": ["bank", "official", "government", "rbi", "sbi"],
        }
        
        detected_intents = []
        content_lower = content.lower()
        
        for intent, keywords in intent_keywords.items():
            if any(kw in content_lower for kw in keywords):
                detected_intents.append(intent)
        
        notes = state.get("engagement_notes", [])
        notes.append(f"Turn {state.get('turn_count', 0)}: Detected intents: {detected_intents}")
        
        return {"engagement_notes": notes}
    
    async def _select_goal(self, state: EngagementState) -> dict:
        """Select the engagement goal based on current state."""
        turn_count = state.get("turn_count", 0)
        intel = state.get("extracted_intelligence", {})
        
        # Progressive goal selection based on turn count and gathered intel
        if turn_count <= 2:
            goal = "build_trust"
        elif not intel.get("upiIds") and not intel.get("bankAccounts"):
            goal = "elicit_upi"
        elif not intel.get("phoneNumbers"):
            goal = "elicit_phone"
        elif not intel.get("phishingLinks"):
            goal = "elicit_link"
        elif turn_count % 3 == 0:
            goal = "stall"  # Occasionally stall to extend engagement
        else:
            goal = "extract_method"
        
        return {"engagement_goal": goal}
    
    async def _generate_response(self, state: EngagementState) -> dict:
        """Generate the victim persona's response."""
        messages = state.get("messages", [])
        persona_dict = state.get("persona")
        goal = state.get("engagement_goal", "build_trust")
        intel = state.get("extracted_intelligence", {})
        
        # Get the latest scammer message
        scammer_msg = ""
        if messages:
            latest = messages[-1]
            if isinstance(latest, HumanMessage):
                scammer_msg = latest.content
            else:
                scammer_msg = str(latest)
        
        # Get persona
        persona_id = state.get("persona_id", "elderly_uncle")
        persona = self.persona_manager.get_persona(persona_id)
        
        # Convert message history to our format
        history = []
        for msg in messages[:-1]:  # Exclude current message
            if isinstance(msg, HumanMessage):
                history.append(Message(
                    sender=SenderType.SCAMMER,
                    text=msg.content,
                    timestamp=datetime.utcnow()
                ))
            elif isinstance(msg, AIMessage):
                history.append(Message(
                    sender=SenderType.USER,
                    text=msg.content,
                    timestamp=datetime.utcnow()
                ))
        
        # Generate response
        response = await self.response_generator.generate_response(
            scammer_message=scammer_msg,
            persona=persona,
            conversation_history=history,
            engagement_goal=goal,
            extracted_intel=intel
        )
        
        return {
            "last_response": response,
            "messages": [AIMessage(content=response)],
            "turn_count": state.get("turn_count", 0) + 1
        }
    
    async def _extract_intel(self, state: EngagementState) -> dict:
        """Extract any intelligence from the conversation."""
        # This is handled by the IntelligenceExtractor service
        # Here we just ensure the state is passed through
        return {}
    
    async def _decide_continue(self, state: EngagementState) -> dict:
        """Decide whether to continue the engagement."""
        turn_count = state.get("turn_count", 0)
        max_turns = self.settings.max_conversation_turns
        
        should_continue = turn_count < max_turns
        
        return {"should_continue": should_continue}
    
    def _should_end(self, state: EngagementState) -> Literal["continue", "end"]:
        """Conditional edge function to determine graph endpoint."""
        if state.get("should_continue", True):
            return "continue"
        return "end"
    
    async def engage(
        self,
        session_id: str,
        scammer_message: str,
        conversation_history: List[Message],
        scam_type: str = "unknown",
        persona_id: Optional[str] = None,
        existing_intel: Optional[ExtractedIntelligence] = None
    ) -> dict:
        """
        Process a scammer message and generate a response.
        
        Args:
            session_id: Unique session identifier
            scammer_message: The scammer's message
            conversation_history: Previous messages
            scam_type: Type of scam detected
            persona_id: Optional specific persona to use
            existing_intel: Already extracted intelligence
            
        Returns:
            Dictionary with response and updated state
        """
        if not self._initialized:
            await self.initialize()
        
        # Select persona based on scam type if not specified
        if not persona_id:
            persona = self.persona_manager.get_persona_for_scam_type(scam_type)
            persona_id = list(self.persona_manager.personas.keys())[
                list(self.persona_manager.personas.values()).index(persona)
            ]
        
        # Build initial state
        messages = []
        for msg in conversation_history:
            if msg.sender == SenderType.SCAMMER:
                messages.append(HumanMessage(content=msg.text))
            else:
                messages.append(AIMessage(content=msg.text))
        
        # Add current scammer message
        messages.append(HumanMessage(content=scammer_message))
        
        initial_state = EngagementState(
            messages=messages,
            session_id=session_id,
            persona_id=persona_id,
            persona=None,
            turn_count=len(conversation_history),
            engagement_goal="build_trust",
            extracted_intelligence=existing_intel.model_dump() if existing_intel else {},
            should_continue=True,
            last_response="",
            scam_type=scam_type,
            engagement_notes=[]
        )
        
        # Run the graph
        # Run the graph
        result = await self.graph.ainvoke(initial_state)
        
        return {
            "response": result.get("last_response", ""),
            "turn_count": result.get("turn_count", 0),
            "should_continue": result.get("should_continue", True),
            "engagement_goal": result.get("engagement_goal", ""),
            "notes": result.get("engagement_notes", [])
        }
