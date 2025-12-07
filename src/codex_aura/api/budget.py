"""Budget allocation API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from ..token_budget.allocator import BudgetAllocator, AllocationStrategy
from ..token_budget.presets import get_preset
from ..models.node import RankedNode
from ..budgeting.analytics import BudgetAnalyticsService
from ..token_budget.counter import ModelName
from .middleware.auth import get_current_user

# Create router
router = APIRouter()


# Models
class User(BaseModel):
    """User model for authentication."""
    id: str
    username: str
    email: Optional[str] = None
    plan: str = "free"  # free, pro, team, enterprise


class BudgetAllocationRequest(BaseModel):
    """Request model for budget allocation."""
    repo_id: str
    nodes: List[RankedNode]
    max_tokens: Optional[int] = None
    strategy: AllocationStrategy = AllocationStrategy.ADAPTIVE
    model: Optional[ModelName] = None

    class Config:
        json_schema_extra = {
            "example": {
                "repo_id": "repo_123",
                "nodes": [
                    {
                        "id": "node_1",
                        "type": "function",
                        "name": "process_data",
                        "path": "src/utils.py",
                        "score": 0.8,
                        "content": "def process_data(data):\n    return data.upper()",
                        "docstring": "Process input data",
                        "signature": "def process_data(data)",
                        "tokens": 50
                    }
                ],
                "max_tokens": 1000,
                "strategy": "greedy",
                "model": "gpt-4"
            }
        }


# Dependency functions
def get_allocator() -> BudgetAllocator:
    """Get budget allocator instance."""
    from ..token_budget.counter import TokenCounter
    counter = TokenCounter()
    return BudgetAllocator(counter)


def get_analytics() -> BudgetAnalyticsService:
    """Get analytics service instance."""
    return BudgetAnalyticsService()




@router.post("/api/v1/budget/allocate")
async def allocate_budget(
    request: BudgetAllocationRequest,
    allocator: BudgetAllocator = Depends(get_allocator),
    analytics: BudgetAnalyticsService = Depends(get_analytics),
    current_user: User = Depends(get_current_user)
) -> dict:  # Using dict instead of AllocationResult for JSON serialization
    """
    Allocate token budget across nodes.

    This is typically called internally by /context endpoint,
    but can be used directly for custom allocation.
    """
    try:
        # Get preset if model specified
        if request.model:
            preset = get_preset(request.model)
            if request.max_tokens is None:
                request.max_tokens = preset.recommended_context

        # Validate max_tokens
        if request.max_tokens is None:
            raise HTTPException(status_code=400, detail="max_tokens is required")

        result = allocator.allocate(
            nodes=request.nodes,
            max_tokens=request.max_tokens,
            strategy=request.strategy,
            model=request.model or ModelName.GPT4
        )

        # Record analytics
        await analytics.record_allocation(
            repo_id=request.repo_id,
            user_id=current_user.id,
            result=result
        )

        # Convert to dict for JSON response
        return {
            "selected_nodes": [
                {
                    "id": node.id,
                    "type": node.type,
                    "name": node.name,
                    "path": node.path,
                    "score": node.score,
                    "content": getattr(node, 'content', ''),
                    "docstring": getattr(node, 'docstring', ''),
                    "signature": getattr(node, 'signature', ''),
                    "tokens": getattr(node, 'tokens', 0)
                }
                for node in result.selected_nodes
            ],
            "total_tokens": result.total_tokens,
            "budget_used_pct": result.budget_used_pct,
            "nodes_included": result.nodes_included,
            "nodes_truncated": result.nodes_truncated,
            "nodes_excluded": result.nodes_excluded,
            "strategy_used": result.strategy_used.value
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Budget allocation failed: {str(e)}")


@router.get("/api/v1/budget/analytics/{user_id}")
async def get_budget_analytics(
    user_id: str,
    period: str = "week",
    analytics: BudgetAnalyticsService = Depends(get_analytics)
):
    """Get budget analytics for a user."""
    try:
        result = await analytics.get_analytics(user_id, period)

        # Convert to dict for JSON response
        return {
            "period": result.period,
            "total_requests": result.total_requests,
            "avg_budget_used_pct": result.avg_budget_used_pct,
            "avg_nodes_included": result.avg_nodes_included,
            "avg_nodes_excluded": result.avg_nodes_excluded,
            "total_tokens_saved": result.total_tokens_saved,
            "tokens_saved_pct": result.tokens_saved_pct,
            "strategy_distribution": result.strategy_distribution
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics retrieval failed: {str(e)}")


@router.get("/api/v1/budget/analytics/{user_id}/summary")
async def get_budget_summary(
    user_id: str,
    analytics: BudgetAnalyticsService = Depends(get_analytics)
):
    """Get budget usage summary for a user."""
    try:
        result = await analytics.get_usage_summary(user_id)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary retrieval failed: {str(e)}")