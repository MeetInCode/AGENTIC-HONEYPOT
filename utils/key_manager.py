"""Centralised round‑robin API key management for Groq and NVIDIA.

Keys are loaded from `config.settings` and rotated in a thread‑safe
round‑robin fashion so that no single key is overused.

Also provides client pooling for AsyncGroq to avoid recreating clients
on every call, reducing overhead.

Configuration (in `.env`):
  - GROQ_API_KEYS   = key1,key2,key3,...
  - NVIDIA_API_KEYS = key1,key2,key3,...

If the pools are empty, we fall back to the per‑agent or shared keys
already configured in `Settings` to keep backwards compatibility.
"""

from __future__ import annotations

import itertools
import threading
from typing import Dict, Iterable, List, Optional

from config.settings import get_settings


_groq_lock = threading.Lock()
_nvidia_lock = threading.Lock()

_groq_cycle: Optional[Iterable[str]] = None
_nvidia_cycle: Optional[Iterable[str]] = None

# Client pools: key -> AsyncGroq client instance
_groq_clients: Dict[str, any] = {}
_groq_clients_lock = threading.Lock()


import logging

_logger = logging.getLogger(__name__)


def _parse_keys(raw: str) -> List[str]:
    """Parse a comma‑separated key string into a clean list."""
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


def _init_groq_cycle() -> None:
    global _groq_cycle
    settings = get_settings()
    keys = _parse_keys(settings.groq_api_keys_raw)

    # Fallback: Check if the single-key variable contains a list (misconfiguration safety)
    if not keys and "," in settings.groq_api_key:
        keys = _parse_keys(settings.groq_api_key)

    if keys:
        _groq_cycle = itertools.cycle(keys)
        _logger.info(f"Groq round-robin pool initialised with {len(keys)} key(s)")
    else:
        _logger.warning("No Groq key pool found — using single key fallback")


def _init_nvidia_cycle() -> None:
    global _nvidia_cycle
    settings = get_settings()
    keys = _parse_keys(settings.nvidia_api_keys_raw)

    # Fallback: Check if the single-key variable contains a list (misconfiguration safety)
    if not keys and "," in settings.nvidia_api_key:
        keys = _parse_keys(settings.nvidia_api_key)

    if keys:
        _nvidia_cycle = itertools.cycle(keys)
        _logger.info(f"NVIDIA round-robin pool initialised with {len(keys)} key(s)")
    else:
        _logger.warning("No NVIDIA key pool found — using single key fallback")


def get_next_groq_key(preferred_fallback: Optional[str] = None) -> str:
    """Return the next Groq API key, using round‑robin if configured.

    Order of precedence:
      1. GROQ_API_KEYS pool (round‑robin)
      2. `preferred_fallback` passed by the caller (e.g. per‑agent key)
      3. Shared `GROQ_API_KEY` from settings
    """
    global _groq_cycle

    # Lazy‑initialise the pool on first use
    if _groq_cycle is None:
        _init_groq_cycle()

    if _groq_cycle is not None:
        with _groq_lock:
            return next(_groq_cycle)

    settings = get_settings()
    if preferred_fallback:
        return preferred_fallback
    return settings.groq_api_key


def get_groq_client(api_key: str):
    """Get or create a cached AsyncGroq client for the given API key.
    
    Reusing clients reduces overhead compared to creating a new client
    for every LLM call. Clients are cached per API key.
    """
    global _groq_clients
    
    with _groq_clients_lock:
        if api_key not in _groq_clients:
            from groq import AsyncGroq
            _groq_clients[api_key] = AsyncGroq(api_key=api_key)
        return _groq_clients[api_key]


def get_next_nvidia_key(preferred_fallback: Optional[str] = None) -> str:
    """Return the next NVIDIA API key, using round‑robin if configured.

    Order of precedence:
      1. NVIDIA_API_KEYS pool (round‑robin)
      2. `preferred_fallback` passed by the caller (e.g. per‑agent key)
      3. Shared `NVIDIA_API_KEY` from settings
    """
    global _nvidia_cycle

    # Lazy‑initialise the pool on first use
    if _nvidia_cycle is None:
        _init_nvidia_cycle()

    if _nvidia_cycle is not None:
        with _nvidia_lock:
            return next(_nvidia_cycle)

    settings = get_settings()
    if preferred_fallback:
        return preferred_fallback
    return settings.nvidia_api_key

