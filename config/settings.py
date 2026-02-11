"""
Application settings — PRD-aligned model configuration.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Environment-based configuration."""

    # ── API Security ──
    api_secret_key: str = Field(default="test-key-123", alias="API_SECRET_KEY")

    # ── Groq Configuration (per-agent keys) ──
    # Backwards-compatible shared key (used as fallback if per-agent keys are not set)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    # Per-agent Groq API keys (allows strict isolation per LLM agent)
    reply_agent_api_key: str = Field(default="", alias="REPLY_AGENT_API_KEY")
    council_llama_scout_api_key: str = Field(default="", alias="COUNCIL_LLAMA_SCOUT_API_KEY")
    council_gpt_oss_api_key: str = Field(default="", alias="COUNCIL_GPT_OSS_API_KEY")

    # PRD-mandated Groq models
    groq_model_scout: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct",
        alias="GROQ_MODEL_SCOUT",
        description="Council Voter 4, Judge, Intelligence Extraction"
    )
    groq_model_engagement: str = Field(
        default="llama-3.3-70b-versatile",
        alias="GROQ_MODEL_ENGAGEMENT",
        description="Council Voter 5, Engagement Response Generator"
    )

    # ── NVIDIA NIM Configuration (per-agent keys) ──
    # Backwards-compatible shared key (used as fallback if per-agent keys are not set)
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        alias="NVIDIA_BASE_URL"
    )
    
    # Updated NVIDIA NIM Models (Validated IDs)
    # Per-agent NVIDIA API keys
    council_nemotron_api_key: str = Field(default="", alias="COUNCIL_NEMOTRON_API_KEY")
    council_multilingual_safety_api_key: str = Field(default="", alias="COUNCIL_MULTILINGUAL_SAFETY_API_KEY")
    council_minimax_api_key: str = Field(default="", alias="COUNCIL_MINIMAX_API_KEY")
    judge_agent_api_key: str = Field(default="", alias="JUDGE_AGENT_API_KEY")

    nvidia_model_judge: str = Field(
        default="nvidia/llama-3.3-nemotron-super-49b-v1.5",
        alias="NVIDIA_MODEL_JUDGE"
    )
    nvidia_model_safety: str = Field(
        default="nvidia/nvidia-nemotron-nano-9b-v2",
        alias="NVIDIA_MODEL_SAFETY",
        description="Council Voter 1 (Safety)"
    )
    nvidia_model_safety_multilingual: str = Field(
        default="meta/llama-3.3-70b-instruct",
        alias="NVIDIA_MODEL_SAFETY_MULTILINGUAL",
        description="Council Voter 2 (Multilingual Safety)"
    )
    nvidia_model_minimax: str = Field(
        default="minimaxai/minimax-m2.1",
        alias="NVIDIA_MODEL_MINIMAX"
    )

    # ── Callback ──
    guvi_callback_url: str = Field(
        default="https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
        alias="GUVI_CALLBACK_URL"
    )

    # ── Application Settings ──
    inactivity_timeout_seconds: int = Field(
        default=5,
        alias="INACTIVITY_TIMEOUT_SECONDS",
        description="Seconds of inactivity before triggering callback (per session)"
    )
    max_conversation_turns: int = Field(default=20, alias="MAX_CONVERSATION_TURNS")
    scam_confidence_threshold: float = Field(default=0.6, alias="SCAM_CONFIDENCE_THRESHOLD")
    
    # ── Server ──
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
