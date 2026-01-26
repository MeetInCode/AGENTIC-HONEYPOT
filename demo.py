"""
Quick Demo Script - Test the Honeypot Detection Council
Run this to test detection without starting the full API server.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel

console = Console()


async def demo_detection():
    """Demonstrate the Detection Council."""
    console.print(Panel.fit(
        "[bold cyan]🍯 Agentic Honeypot - Detection Council Demo[/bold cyan]",
        border_style="cyan"
    ))
    
    # Import after path setup
    from agents.detection_council import DetectionCouncil
    from services.intelligence_extractor import IntelligenceExtractor
    
    # Initialize
    console.print("\n[bold]Initializing Detection Council...[/bold]")
    council = DetectionCouncil()
    await council.initialize()
    
    console.print("[bold]Initializing Intelligence Extractor...[/bold]")
    extractor = IntelligenceExtractor()
    await extractor.initialize()
    
    # Test messages
    test_messages = [
        "Your bank account will be blocked today. Verify immediately by clicking: http://sbi-verify.xyz",
        "URGENT: Share your UPI PIN to avoid account suspension. Contact: scammer@ybl or call +91-9876543210",
        "Hi, let's meet for coffee tomorrow at 3 PM. Looking forward to it!",
        "Congratulations! You won Rs 50,00,000 in lottery. Share bank account number to receive prize.",
        "Your Amazon order #12345 has shipped. Track at amazon.in",
    ]
    
    console.print("\n" + "=" * 60)
    
    for i, message in enumerate(test_messages, 1):
        console.print(f"\n[bold yellow]Test {i}:[/bold yellow]")
        console.print(f"[dim]{message}[/dim]")
        
        # Analyze with council
        verdict = await council.analyze(message)
        
        # Extract intelligence
        intel = await extractor.extract(message)
        
        # Show intelligence if found
        if not intel.is_empty():
            console.print("\n[bold magenta]📊 Extracted Intelligence:[/bold magenta]")
            if intel.upiIds:
                console.print(f"  📱 UPI IDs: {intel.upiIds}")
            if intel.phoneNumbers:
                console.print(f"  📞 Phones: {intel.phoneNumbers}")
            if intel.phishingLinks:
                console.print(f"  🔗 Links: {intel.phishingLinks}")
            if intel.suspiciousKeywords:
                console.print(f"  ⚠️ Keywords: {intel.suspiciousKeywords[:5]}")
        
        console.print("\n" + "-" * 60)
    
    console.print("\n[bold green]✅ Demo completed![/bold green]\n")


if __name__ == "__main__":
    asyncio.run(demo_detection())
