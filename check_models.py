"""
Script to test connectivity and availability of all configured Groq and NVIDIA models.
"""

import asyncio
import os
from rich.console import Console
from rich.table import Table
from groq import AsyncGroq
from openai import AsyncOpenAI
from config.settings import get_settings

console = Console()

async def test_model_connectivity():
    settings = get_settings()
    
    console.print("\n[bold cyan]🧪 Testing Model Connectivity[/bold cyan]")
    console.print("=" * 60)
    
    results = []
    
    # --- Test Groq Models ---
    groq_models = [
        ("Groq Detection", settings.groq_model_detection),
        ("Groq Engagement", settings.groq_model_engagement),
        ("Groq Summarizer", settings.groq_model_summarizer),
    ]
    
    if settings.groq_api_key:
        groq_client = AsyncGroq(api_key=settings.groq_api_key)
        
        # Prepare NVIDIA client for fallback
        nv_client_fallback = None
        if settings.nvidia_api_key:
            nv_client_fallback = AsyncOpenAI(
                base_url=settings.nvidia_base_url,
                api_key=settings.nvidia_api_key
            )

        for name, model_id in groq_models:
            console.print(f"Testing [blue]{name}[/blue] ({model_id})...")
            try:
                # Check if this is actually an NVIDIA model masquerading in Groq settings
                is_nvidia = "openai/" in model_id or "meta/" in model_id or "mistralai/" in model_id or "deepseek" in model_id
                
                if is_nvidia and nv_client_fallback:
                     chat_completion = await nv_client_fallback.chat.completions.create(
                        messages=[{"role": "user", "content": "Hello."}],
                        model=model_id,
                        max_tokens=5,
                    )
                else:
                    chat_completion = await groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": "Hello, are you online? Reply with YES only."}],
                        model=model_id,
                        max_tokens=10,
                    )
                
                response = chat_completion.choices[0].message.content
                status = "[green]ONLINE[/green]" if response else "[yellow]NO RESPONSE[/yellow]"
                results.append((name, model_id, status, "Success"))
            except Exception as e:
                results.append((name, model_id, "[red]OFFLINE[/red]", str(e)[:100]))
    else:
        for name, model_id in groq_models:
            results.append((name, model_id, "[red]SKIPPED[/red]", "Missing API Key"))

    # --- Test NVIDIA Models ---
    nvidia_models = [
        ("NVIDIA Mistral", settings.nvidia_model_mistral),
        ("NVIDIA Multilingual Safety", settings.nvidia_model_safety_multilingual),
        ("NVIDIA General", settings.nvidia_model_general),
    ]
    
    if settings.nvidia_api_key:
        nv_client = AsyncOpenAI(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key
        )
        
        for name, model_id in nvidia_models:
            console.print(f"Testing [green]{name}[/green] ({model_id})...")
            try:
                # Use a very simple prompt to minimize token usage/latency
                response = await nv_client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": "Ping"}],
                    max_tokens=5,
                    temperature=0.1
                )
                content = response.choices[0].message.content
                status = "[green]ONLINE[/green]" if content else "[yellow]NO RESPONSE[/yellow]"
                results.append((name, model_id, status, "Success"))
            except Exception as e:
                # NVIDIA NIMs can sometimes return specific error codes for model loading
                error_msg = str(e)
                if "404" in error_msg:
                    status = "[red]NOT FOUND[/red]" 
                elif "503" in error_msg:
                    status = "[yellow]LOADING[/yellow]" 
                else:
                    status = "[red]ERROR[/red]"
                results.append((name, model_id, status, error_msg[:100]))
    else:
        for name, model_id in nvidia_models:
            results.append((name, model_id, "[red]SKIPPED[/red]", "Missing API Key"))
            
    # --- Display Results ---
    table = Table(title="Model Availability Report")
    table.add_column("Service Name", style="cyan")
    table.add_column("Model ID", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="italic")
    
    for name, mid, status, details in results:
        table.add_row(name, mid, status, details)
        
    console.print("\n")
    console.print(table)
    console.print("\n")

if __name__ == "__main__":
    asyncio.run(test_model_connectivity())
