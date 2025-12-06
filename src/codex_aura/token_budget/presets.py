"""Token budget presets for different LLM models."""

from dataclasses import dataclass

from fastapi import APIRouter

@dataclass
class ModelBudgetPreset:
    model: str
    context_window: int       # Total context window
    recommended_context: int  # Recommended for context (留 room for response)
    max_context: int          # Maximum safe context
    chars_per_token: float    # For quick estimates

BUDGET_PRESETS: dict[str, ModelBudgetPreset] = {
    "gpt-4": ModelBudgetPreset(
        model="gpt-4",
        context_window=8192,
        recommended_context=4000,
        max_context=6000,
        chars_per_token=4.0
    ),
    "gpt-4-turbo": ModelBudgetPreset(
        model="gpt-4-turbo",
        context_window=128000,
        recommended_context=16000,
        max_context=64000,
        chars_per_token=4.0
    ),
    "gpt-4o": ModelBudgetPreset(
        model="gpt-4o",
        context_window=128000,
        recommended_context=16000,
        max_context=64000,
        chars_per_token=4.0
    ),
    "gpt-3.5-turbo": ModelBudgetPreset(
        model="gpt-3.5-turbo",
        context_window=16385,
        recommended_context=8000,
        max_context=12000,
        chars_per_token=4.0
    ),
    "claude-3-opus": ModelBudgetPreset(
        model="claude-3-opus",
        context_window=200000,
        recommended_context=32000,
        max_context=100000,
        chars_per_token=3.5
    ),
    "claude-3.5-sonnet": ModelBudgetPreset(
        model="claude-3.5-sonnet",
        context_window=200000,
        recommended_context=32000,
        max_context=100000,
        chars_per_token=3.5
    ),
    "claude-3-haiku": ModelBudgetPreset(
        model="claude-3-haiku",
        context_window=200000,
        recommended_context=16000,
        max_context=50000,
        chars_per_token=3.5
    ),
}

def get_preset(model: str) -> ModelBudgetPreset:
    """Get budget preset for model, with fallback."""
    # Exact match
    if model in BUDGET_PRESETS:
        return BUDGET_PRESETS[model]

    # Partial match
    for key, preset in BUDGET_PRESETS.items():
        if key in model or model in key:
            return preset

    # Default fallback
    return BUDGET_PRESETS["gpt-4"]

# API endpoint
router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])

@router.get("/presets")
async def list_presets() -> dict[str, ModelBudgetPreset]:
    return BUDGET_PRESETS

@router.get("/presets/{model}")
async def get_model_preset(model: str) -> ModelBudgetPreset:
    return get_preset(model)