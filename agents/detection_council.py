"""
Detection Council
Orchestrates all detection agents and produces final verdicts.
"""

import asyncio
from typing import List, Optional
from rich.console import Console
from rich.table import Table

from .base_agent import BaseDetectionAgent
from .rule_guard import RuleGuardAgent
from .fast_ml import FastMLAgent
from .bert_lite import BertLiteAgent
from .lex_judge import LexJudgeAgent
from .outlier_sentinel import OutlierSentinelAgent
from .context_seer import ContextSeerAgent
from .meta_moderator import MetaModeratorAgent
from models.schemas import Message, CouncilVote, CouncilVerdict


console = Console()


class DetectionCouncil:
    """
    Orchestrates the Detection Council - a multi-model ensemble
    for scam detection. Coordinates all agents and produces
    aggregated verdicts.
    """
    
    def __init__(self):
        """Initialize all council members."""
        self.agents: List[BaseDetectionAgent] = [
            RuleGuardAgent(),
            FastMLAgent(),
            BertLiteAgent(),
            LexJudgeAgent(),
            OutlierSentinelAgent(),
            ContextSeerAgent(),
        ]
        self.meta_moderator = MetaModeratorAgent()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all council agents."""
        if self._initialized:
            return
        
        console.print("[bold blue]🏛️ Initializing Detection Council...[/bold blue]")
        
        # Initialize all agents in parallel
        init_tasks = [agent.initialize() for agent in self.agents]
        init_tasks.append(self.meta_moderator.initialize())
        
        await asyncio.gather(*init_tasks, return_exceptions=True)
        
        self._initialized = True
        console.print("[bold green]✅ Detection Council ready![/bold green]")
    
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVerdict:
        """
        Analyze a message using all council members.
        
        Args:
            message: The message to analyze
            conversation_history: Previous messages in the conversation
            metadata: Additional context (channel, language, locale)
            
        Returns:
            CouncilVerdict with final decision and all votes
        """
        if not self._initialized:
            await self.initialize()
        
        console.print(f"\n[bold yellow]🔍 Analyzing message:[/bold yellow] {message[:100]}...")
        
        # Collect votes from all agents in parallel
        vote_tasks = [
            agent.analyze(message, conversation_history, metadata)
            for agent in self.agents
        ]
        
        votes: List[CouncilVote] = await asyncio.gather(
            *vote_tasks, 
            return_exceptions=True
        )
        
        # Filter out exceptions and keep valid votes
        valid_votes = [
            vote for vote in votes 
            if isinstance(vote, CouncilVote)
        ]
        
        # Log any failed votes
        for i, result in enumerate(votes):
            if isinstance(result, Exception):
                console.print(
                    f"[red]⚠️ {self.agents[i].name} failed: {result}[/red]"
                )
        
        # Get final verdict from meta-moderator
        verdict = await self.meta_moderator.aggregate_votes(valid_votes)
        
        # Display results
        self._display_verdict(verdict)
        
        return verdict
    
    def _display_verdict(self, verdict: CouncilVerdict) -> None:
        """Display the council verdict in a formatted table."""
        # Create votes table
        table = Table(title="🏛️ Detection Council Votes")
        table.add_column("Agent", style="cyan")
        table.add_column("Type", style="dim")
        table.add_column("Verdict", style="bold")
        table.add_column("Confidence", justify="right")
        table.add_column("Key Indicators", style="italic")
        
        for vote in verdict.votes:
            verdict_cell = "[red]🚨 SCAM[/red]" if vote.is_scam else "[green]✅ SAFE[/green]"
            confidence_cell = f"{vote.confidence:.0%}"
            features = ", ".join(vote.features[:3]) if vote.features else "-"
            
            table.add_row(
                vote.agent_name,
                vote.agent_type,
                verdict_cell,
                confidence_cell,
                features[:50] + "..." if len(features) > 50 else features
            )
        
        console.print(table)
        
        # Display final verdict
        if verdict.is_scam:
            console.print(
                f"\n[bold red]🚨 FINAL VERDICT: SCAM DETECTED "
                f"(Confidence: {verdict.confidence:.0%})[/bold red]"
            )
        else:
            console.print(
                f"\n[bold green]✅ FINAL VERDICT: SAFE "
                f"(Confidence: {verdict.confidence:.0%})[/bold green]"
            )
        
        console.print(f"[dim]{verdict.justification}[/dim]")
    
    async def cleanup(self) -> None:
        """Cleanup all agent resources."""
        cleanup_tasks = [agent.cleanup() for agent in self.agents]
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
