"""Token budget presets for different LLM models."""

from typing import Dict, Any


# Budget presets for different models
BUDGET_PRESETS: Dict[str, Dict[str, Any]] = {
    "gpt-4-turbo": {
        "context_window": 128000,
        "recommended_context": 8000,
        "max_context": 32000
    },
    "gpt-3.5-turbo": {
        "context_window": 16000,
        "recommended_context": 4000,
        "max_context": 8000
    },
    "claude-3-opus": {
        "context_window": 200000,
        "recommended_context": 16000,
        "max_context": 64000
    },
    "claude-3-sonnet": {
        "context_window": 200000,
        "recommended_context": 12000,
        "max_context": 48000
    },
    "claude-3-haiku": {
        "context_window": 200000,
        "recommended_context": 8000,
        "max_context": 32000
    },
    "gpt-4": {
        "context_window": 8192,
        "recommended_context": 4000,
        "max_context": 6000
    },
    "gpt-4o": {
        "context_window": 128000,
        "recommended_context": 8000,
        "max_context": 32000
    },
    "gpt-4o-mini": {
        "context_window": 128000,
        "recommended_context": 6000,
        "max_context": 24000
    }
}


def get_budget_preset(model: str) -> Dict[str, Any]:
    """Get budget preset for a specific model.

    Args:
        model: Model name (e.g., 'gpt-4-turbo')

    Returns:
        Budget preset dictionary with context_window, recommended_context, max_context

    Raises:
        ValueError: If model is not supported
    """
    if model not in BUDGET_PRESETS:
        available_models = list(BUDGET_PRESETS.keys())
        raise ValueError(f"Unsupported model '{model}'. Available models: {available_models}")

    return BUDGET_PRESETS[model].copy()


def get_all_presets() -> Dict[str, Dict[str, Any]]:
    """Get all available budget presets."""
    return BUDGET_PRESETS.copy()


def validate_budget_params(model: str, max_tokens: int) -> None:
    """Validate budget parameters against model constraints.

    Args:
        model: Model name
        max_tokens: Maximum tokens requested

    Raises:
        ValueError: If parameters are invalid
    """
    preset = get_budget_preset(model)

    if max_tokens > preset["context_window"]:
        raise ValueError(
            f"max_tokens ({max_tokens}) exceeds model's context window "
            f"({preset['context_window']}) for model '{model}'"
        )

    if max_tokens < 100:
        raise ValueError("max_tokens must be at least 100")