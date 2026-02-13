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
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_api_keys_raw: str = Field(default="", alias="GROQ_API_KEYS")

    reply_agent_api_key: str = Field(default="", alias="REPLY_AGENT_API_KEY")
    council_llama_scout_api_key: str = Field(default="", alias="COUNCIL_LLAMA_SCOUT_API_KEY")
    council_gpt_oss_api_key: str = Field(default="", alias="COUNCIL_GPT_OSS_API_KEY")
    
    # Judge Key (defaults to main GROQ_API_KEY if not distinct)
    judge_agent_api_key: str = Field(default="", alias="JUDGE_AGENT_API_KEY")

    # ── PRD-mandated Groq models ──
    # Judge - OPTIMIZED FOR CONCURRENCY (Fast Inference)
    groq_model_judge: str = Field(
        default="llama-3.3-70b-versatile",
        alias="GROQ_MODEL_JUDGE"
    )
    # Reply Agent
    groq_model_engagement: str = Field(
        default="llama-3.3-70b-versatile",
        alias="GROQ_MODEL_ENGAGEMENT"
    )
    # Council Member 1 & 5 (Scout)
    groq_model_scout: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct",
        alias="GROQ_MODEL_SCOUT"
    )
    # Council Member 2 (GPT-OSS)
    groq_model_gpt_oss: str = Field(
        default="openai/gpt-oss-120b",
        alias="GROQ_MODEL_GPT_OSS"
    )
    
    # ── NVIDIA NIM Configuration (per-agent keys) ──
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_api_keys_raw: str = Field(default="", alias="NVIDIA_API_KEYS")
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        alias="NVIDIA_BASE_URL"
    )
    
    council_nemotron_api_key: str = Field(default="", alias="COUNCIL_NEMOTRON_API_KEY")
    council_minimax_api_key: str = Field(default="", alias="COUNCIL_MINIMAX_API_KEY")

    # Council Member 3 (Nemotron)
    nvidia_model_nemotron: str = Field(
        default="nvidia/llama-3.3-nemotron-super-49b-v1",
        alias="NVIDIA_MODEL_NEMOTRON"
    )
    # Council Member 4 (Minimax) - UPDATED TO use m2.1
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
        default=20,
        alias="INACTIVITY_TIMEOUT_SECONDS"
    )
    max_conversation_turns: int = Field(default=20, alias="MAX_CONVERSATION_TURNS")
    scam_confidence_threshold: float = Field(default=0.6, alias="SCAM_CONFIDENCE_THRESHOLD")
    
    
    # ── Server ──
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    workers: int = Field(
        default=1,
        alias="WORKERS",
        description="Number of worker processes for production (default: 1, use 4+ for production)"
    )
    
    # ── Request Limits ──
    max_message_length: int = Field(
        default=10000,
        alias="MAX_MESSAGE_LENGTH",
        description="Maximum message text length (characters)"
    )
    request_timeout: float = Field(
        default=30.0,
        alias="REQUEST_TIMEOUT",
        description="Request timeout in seconds"
    )

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
