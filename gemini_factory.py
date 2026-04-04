"""
Gemini Factory for DSPy

Creates DspyModelConfig instances for Google Gemini models using LiteLLM's
gemini/ provider format (e.g., "gemini/gemini-2.5-flash").

Environment: GEMINI_API_KEY
"""

import os
from typing import Optional

import dspy
from dotenv import load_dotenv

from dspy_factory import DspyModelConfig

load_dotenv()

# Static registry: model_id → (context_window, max_output_tokens)
_GEMINI_MODELS = {
    "gemini/gemini-2.5-pro":                        (1_048_576, 65_536),
    "gemini/gemini-2.5-flash":                      (1_048_576, 65_535),
    "gemini/gemini-2.5-flash-lite-preview-09-2025": (1_048_576, 65_535),
    "gemini/gemini-2.0-flash":                      (1_048_576,  8_192),
    "gemini/gemini-1.5-pro":                        (2_097_152,  8_192),
    "gemini/gemini-1.5-flash":                      (1_048_576,  8_192),
}


def get_gemini_model(model_name: str, temp: float = 0.0) -> Optional[DspyModelConfig]:
    """
    Resolve a Gemini model config by name.

    Accepts:
      - Exact LiteLLM format: "gemini/gemini-2.5-flash"
      - No prefix:            "gemini-2.5-flash"
      - Partial match:        "2.5-flash"  (matches first registry key containing the string)
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment variables")
        return None

    # Normalise: ensure "gemini/" prefix for lookup
    normalized = model_name if model_name.startswith("gemini/") else f"gemini/{model_name}"

    # Exact match first
    if normalized in _GEMINI_MODELS:
        model_id = normalized
    else:
        # Partial match against registry keys
        lower = model_name.lower()
        matches = [k for k in _GEMINI_MODELS if lower in k.lower()]
        if not matches:
            print(f"❌ No Gemini model found matching '{model_name}'")
            return None
        model_id = matches[0]

    context_window, max_output = _GEMINI_MODELS[model_id]

    try:
        dspy_lm = dspy.LM(
            model=model_id,
            max_tokens=max_output,
            temperature=temp,
            api_key=api_key,
        )
    except Exception as e:
        print(f"❌ Failed to create DSPy LM for {model_id}: {e}")
        return None

    return DspyModelConfig(
        name=model_id,
        dspy_lm=dspy_lm,
        context_window=context_window,
        max_output_tokens=max_output,
        cost_per_token=0.0,
        provider="google",
        description=model_id.split("/")[-1],
        temp=temp,
    )


if __name__ == "__main__":
    print("Testing Gemini Model Factory...")
    print("=" * 50)

    test_models = [
        "gemini/gemini-2.5-pro",
        "gemini-2.5-flash",
        "2.5-flash",
        "nonexistent-model",
    ]

    for model_name in test_models:
        print(f"\n🔍 Testing: {model_name}")
        config = get_gemini_model(model_name)

        if config:
            print(f"✅ Found: {config.name}")
            print(f"   Description: {config.description}")
            print(f"   Context: {config.context_window:,} tokens")
            print(f"   Max output: {config.max_output_tokens:,} tokens")
        else:
            print(f"❌ Not found")
