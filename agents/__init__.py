"""Agents package — LLM-only detection council."""

from agents.detection_council import DetectionCouncil
from agents.nvidia_agents import MinimaxVoter, NemotronVoter
from agents.groq_agents import (
    LlamaScoutVoter, 
    GptOssVoter, 
)
from agents.meta_moderator import JudgeAgent

__all__ = [
    "DetectionCouncil",
    "MinimaxVoter", "NemotronVoter",
    "LlamaScoutVoter", "GptOssVoter",
    "JudgeAgent",
]
