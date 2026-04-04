"""
Simplified DSPy Factory for OpenRouter Models

This module provides a simple function to fetch OpenRouter model configurations
and create DSPy LM instances. It queries the live OpenRouter API to get current
model information and pricing.
"""

import os
import requests
from typing import Dict, Any, Optional
import dspy
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class DspyModelConfig:
    """Represents a configuration for a DSPy model."""

    name: str
    dspy_lm: dspy.LM
    context_window: int
    max_output_tokens: int
    cost_per_token: float
    provider: str
    description: str
    temp: float


def get_openrouter_model(
    model_name: str, temp: float = 0.0
) -> Optional[DspyModelConfig]:
    """
    Get OpenRouter model configuration by querying the live API.

    Args:
        model_name: The model name to search for (e.g., "anthropic/claude-3-sonnet")
                   Can be exact match or partial match

    Returns:
        DspyModelConfig: Model configuration in the specified format, or None if not found.
    """
    try:
        # Fetch models from OpenRouter API
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        response.raise_for_status()

        models_data = response.json()
        if "data" not in models_data:
            print(f"❌ Unexpected API response format")
            return None

        models = models_data["data"]

        # Find matching models
        matching_models = []
        model_name_lower = model_name.lower()

        for model in models:
            model_id = model.get("id", "").lower()

            # Check for exact match first
            if model_id == model_name_lower:
                matching_models = [model]  # Exact match takes priority
                break

            # Check for partial match
            if model_name_lower in model_id:
                matching_models.append(model)

        if not matching_models:
            print(f"❌ No models found matching '{model_name}'")
            return None

        # If multiple matches, select the cheapest one
        selected_model = None
        lowest_cost = float("inf")

        for model in matching_models:
            # Extract pricing information
            pricing = model.get("pricing", {})
            prompt_cost = pricing.get("prompt", "0")

            try:
                cost = float(prompt_cost)
                if cost < lowest_cost:
                    lowest_cost = cost
                    selected_model = model
            except (ValueError, TypeError):
                # If cost parsing fails, skip this model
                continue

        if selected_model is None:
            # Fallback to first model if cost comparison fails
            selected_model = matching_models[0]
            pricing = selected_model.get("pricing", {})
            lowest_cost = float(pricing.get("prompt", "0"))

        # Extract model information
        model_id = selected_model.get("id", "")
        if model_id:
            model_id = f"openrouter/{model_id}"
        context_length = selected_model.get("context_length", 4096)

        # Get max output tokens (use a reasonable default if not specified)
        max_output = max(4096, context_length // 2)  # Used to be 4, too small

        # Create DSPy LM instance
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("❌ OPENROUTER_API_KEY not found in environment variables")
            return None

        try:
            dspy_lm = dspy.LM(
                model=model_id,
                max_tokens=max_output,
                temperature=temp,
                api_key=api_key,
                # extras={"transforms": "[middle-out]"}
            )
        except Exception as e:
            print(f"❌ Failed to create DSPy LM for {model_id}: {e}")
            return None

        # Build description
        model_name_display = selected_model.get("name", model_id)
        description = f"{model_name_display}"

        # Return a DspyModelConfig instance with the model configuration
        return DspyModelConfig(
            name=model_id,
            dspy_lm=dspy_lm,
            context_window=context_length,
            max_output_tokens=max_output,
            cost_per_token=lowest_cost,
            provider="openrouter",
            description=description,
            temp=temp,
        )
    except requests.RequestException as e:
        print(f"❌ Failed to fetch models from OpenRouter API: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


if __name__ == "__main__":
    # Test the function
    print("Testing OpenRouter Model Factory...")
    print("=" * 50)

    # Test cases
    test_models = [
        "anthropic/claude-3-sonnet",
        "claude",  # Partial match
        "gpt-4o",  # Partial match
        "nonexistent-model",  # Should return None
    ]

    for model_name in test_models:
        print(f"\n🔍 Testing: {model_name}")
        config = get_openrouter_model(model_name)

        if config:
            print(f"✅ Found: {config.name}")
            print(f"   Description: {config.description}")
            print(f"   Context: {config.context_window:,} tokens")
            print(f"   Max output: {config.max_output_tokens:,} tokens")
            print(f"   Cost: ${config.cost_per_token:.6f} per token")
        else:
            print(f"❌ Not found")
