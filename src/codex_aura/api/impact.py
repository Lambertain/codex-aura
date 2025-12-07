"""API endpoints for impact analysis."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from ..impact_engine import ImpactEngine

router = APIRouter(prefix="/api/v1/impact", tags=["impact"])


class ImpactRequest(BaseModel):
    """Request model for impact analysis."""

    file_path: str
    repo_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "src/utils.py",
                "repo_id": "repo_abc123"
            }
        }


class ImpactResponse(BaseModel):
    """Response model for impact analysis."""

    impacted_files: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "impacted_files": ["src/main.py", "tests/test_utils.py"]
            }
        }


@router.post("/", response_model=ImpactResponse)
async def analyze_impact(request: ImpactRequest):
    """
    Analyze impact of changes to a file.

    Returns a list of files that would be impacted by changes to the specified file,
    based on rule-based dependency analysis (imports, function calls, class inheritance).

    The analysis uses depth-limited traversal (max depth 3) for performance.
    """
    try:
        # For now, assume repo_id is the path to the repository
        # In a real implementation, this would be resolved from a database
        repo_path = request.repo_id  # This is a simplification

        engine = ImpactEngine(repo_path)
        impacted_files = engine.predict(request.file_path, request.repo_id)

        return ImpactResponse(impacted_files=impacted_files)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Impact analysis failed: {str(e)}")