"""
Configuration settings for the Agentic Honeypot system.
Loads environment variables and provides type-safe configuration.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Security
    api_secret_key: str = Field(..., env="API_SECRET_KEY")
    
    # Groq API Configuration
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    groq_model_detection: str = Field(
        default="llama-3.3-70b-versatile", 
        env="GROQ_MODEL_DETECTION"
    )
    groq_model_engagement: str = Field(
        default="openai/gpt-oss-120b", 
        env="GROQ_MODEL_ENGAGEMENT"
    )
    groq_model_summarizer: str = Field(
        default="llama-3.3-70b-versatile", 
        env="GROQ_MODEL_SUMMARIZER"
    )
    
    # NVIDIA NIM Configuration (Optional)
    nvidia_api_key: Optional[str] = Field(default=None, env="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        env="NVIDIA_BASE_URL"
    )
    nvidia_model_mistral: str = Field(
        default="mistralai/mistral-large-3-675b-instruct-2512",
        env="NVIDIA_MODEL_MISTRAL"
    )
    nvidia_model_deepseek: str = Field(
        default="deepseek-ai/deepseek-v3.1",
        env="NVIDIA_MODEL_DEEPSEEK"
    )
    nvidia_model_general: str = Field(
        default="openai/gpt-oss-120b",
        env="NVIDIA_MODEL_GENERAL"
    )
    
    # GUVI Callback Configuration
    guvi_callback_url: str = Field(
        default="https://hackathon.guvi.in/api/updateHoneyPotFinalResult",
        env="GUVI_CALLBACK_URL"
    )
    
    # Database Configuration
    database_url: str = Field(
        default="sqlite:///./honeypot.db",
        env="DATABASE_URL"
    )
    
    # Application Settings
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    max_conversation_turns: int = Field(default=20, env="MAX_CONVERSATION_TURNS")
    scam_confidence_threshold: float = Field(
        default=0.6, 
        env="SCAM_CONFIDENCE_THRESHOLD"
    )
    
    # Rate Limiting
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period_seconds: int = Field(default=60, env="RATE_LIMIT_PERIOD_SECONDS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()
