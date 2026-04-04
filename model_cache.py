"""
Thread-safe cache for resolved DspyModelConfig instances.

Avoids repeated API calls for the same model name + temperature combination.
Routes to Gemini factory for "gemini/" prefixed models, OpenRouter for all others.
"""

import threading
from typing import Dict, Optional, Tuple

from dspy_factory import get_openrouter_model, DspyModelConfig
from gemini_factory import get_gemini_model

DEFAULT_MODEL_NAME = "moonshotai/kimi-k2-thinking"  # CLI default (OpenRouter)
API_DEFAULT_MODEL_NAME = "gemini/gemini-2.5-flash"  # API default (Gemini)

_cache: Dict[Tuple[str, float], DspyModelConfig] = {}
_lock = threading.Lock()


def get_cached_model(model_name: str, temp: float = 0.0) -> Optional[DspyModelConfig]:
    """Return a cached DspyModelConfig, resolving via the appropriate factory on first call."""
    key = (model_name, temp)
    with _lock:
        if key in _cache:
            return _cache[key]

    # Resolve outside the lock — API call can be slow
    if model_name.startswith("gemini/"):
        config = get_gemini_model(model_name, temp=temp)
    else:
        config = get_openrouter_model(model_name, temp=temp)

    if config is not None:
        with _lock:
            _cache[key] = config

    return config


def resolve_model_cached(
    primary: Optional[str],
    fallback: Optional[str],
    temp: float = 0.0,
) -> DspyModelConfig:
    """
    Try primary model, then fallback, then DEFAULT_MODEL_NAME.
    Raises RuntimeError if none can be resolved.
    """
    for name in [primary, fallback, DEFAULT_MODEL_NAME]:
        if name:
            cfg = get_cached_model(name, temp=temp)
            if cfg is not None:
                return cfg
    raise RuntimeError(
        f"Could not resolve any model. Tried: {primary!r}, {fallback!r}, {DEFAULT_MODEL_NAME!r}"
    )
