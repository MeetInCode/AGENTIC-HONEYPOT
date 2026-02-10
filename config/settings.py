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

    # ── Groq Configuration ──
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    
    # PRD-mandated Groq models
    groq_model_scout: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct",
        alias="GROQ_MODEL_SCOUT",
        description="Council Voter 4, Judge, Intelligence Extraction"
    )
    groq_model_engagement: str = Field(
        default="openai/gpt-oss-120b",
        alias="GROQ_MODEL_ENGAGEMENT",
        description="Council Voter 5, Engagement Response Generator"
    )

    # ── NVIDIA NIM Configuration ──
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        alias="NVIDIA_BASE_URL"
    )
    
    # PRD-mandated NVIDIA models
    nvidia_model_nemotron: str = Field(
        default="nvidia/llama-3.3-nemotron-super-49b-v1",
        alias="NVIDIA_MODEL_NEMOTRON",
        description="Council Voter 1"
    )
    nvidia_model_deepseek: str = Field(
        default="deepseek-ai/deepseek-v3",
        alias="NVIDIA_MODEL_DEEPSEEK",
        description="Council Voter 2"
    )
    nvidia_model_minimax: str = Field(
        default="minimax/minimax-m2",
        alias="NVIDIA_MODEL_MINIMAX",
        description="Council Voter 3"
    )

    # ── Callback ──
    guvi_callback_url: str = Field(
        default="https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
        alias="GUVI_CALLBACK_URL"
    )

    # ── Application Settings ──
    inactivity_timeout_seconds: int = Field(
        default=30, alias="INACTIVITY_TIMEOUT_SECONDS",
        description="Seconds of inactivity before triggering callback"
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
