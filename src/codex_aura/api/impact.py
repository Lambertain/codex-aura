"""API endpoints for impact analysis."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Literal

from ..impact_engine import ImpactEngine
from ..storage.sqlite import SQLiteStorage

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


class PRImpactRequest(BaseModel):
    """Request model for PR impact analysis."""

    repo_id: str
    changed_files: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "repo_id": "repo_abc123",
                "changed_files": ["src/utils.py", "src/models.py"]
            }
        }


class PRImpactResponse(BaseModel):
    """Response model for PR impact analysis."""

    impacted_files: List[str]
    risk_level: Literal["low", "medium", "high"]
    comment: str

    class Config:
        json_schema_extra = {
            "example": {
                "impacted_files": ["src/main.py", "tests/test_utils.py", "src/api.py"],
                "risk_level": "medium",
                "comment": "## Impact Analysis\n\n**Changed Files:** 2\n**Impacted Files:** 3\n**Risk Level:** Medium\n\n### Details\n- Direct impact: src/main.py, src/api.py\n- Test impact: tests/test_utils.py\n\n### Recommendations\n- Review API changes carefully\n- Run full test suite"
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


@router.post("/pr", response_model=PRImpactResponse)
async def analyze_pr_impact(request: PRImpactRequest):
    """
    Analyze impact of changes in a pull request.

    Returns impacted files, risk level assessment, and a formatted comment
    for PR discussion based on dependency analysis.
    """
    try:
        storage = SQLiteStorage()
        graph = storage.load_graph(request.repo_id)

        if not graph:
            raise HTTPException(status_code=404, detail=f"Repository graph '{request.repo_id}' not found")

        # Analyze impact for each changed file
        all_impacted = set()
        direct_impacted = set()
        test_impacted = set()

        for changed_file in request.changed_files:
            # Validate changed file exists in graph
            if not any(n.path == changed_file for n in graph.nodes if n.type == "file"):
                continue  # Skip files not in graph

            # Find all nodes in the changed file
            changed_file_nodes = [n for n in graph.nodes if n.path == changed_file]

            for node in changed_file_nodes:
                # Find incoming edges (who imports/calls this node)
                incoming_edges = [e for e in graph.edges if e.target == node.id]

                for edge in incoming_edges:
                    # Find the file containing the source node
                    source_node = next((n for n in graph.nodes if n.id == edge.source), None)
                    if source_node and source_node.path not in request.changed_files:
                        all_impacted.add(source_node.path)
                        direct_impacted.add(source_node.path)

                        # Check if it's a test file
                        if source_node.path.startswith(('test_', 'tests/', 'test/')) or 'test' in source_node.path.lower():
                            test_impacted.add(source_node.path)

        # Transitive impact (simplified - up to depth 2)
        transitive_impacted = set()
        for impacted_path in direct_impacted:
            impacted_file_nodes = [n for n in graph.nodes if n.path == impacted_path]

            for node in impacted_file_nodes:
                incoming_edges = [e for e in graph.edges if e.target == node.id]

                for edge in incoming_edges:
                    source_node = next((n for n in graph.nodes if n.id == edge.source), None)
                    if (source_node and
                        source_node.path not in all_impacted and
                        source_node.path not in request.changed_files):
                        transitive_impacted.add(source_node.path)

        all_impacted.update(transitive_impacted)

        # Calculate risk level
        total_impacted = len(all_impacted)
        changed_count = len(request.changed_files)

        if total_impacted == 0:
            risk_level = "low"
        elif total_impacted <= 5 and changed_count <= 3:
            risk_level = "low"
        elif total_impacted <= 15 or changed_count <= 5:
            risk_level = "medium"
        else:
            risk_level = "high"

        # Check for critical files
        critical_patterns = ['__init__.py', 'main.py', 'app.py', 'api/', 'core/', 'config/']
        has_critical = any(any(pattern in f for pattern in critical_patterns) for f in all_impacted)

        if has_critical and risk_level == "low":
            risk_level = "medium"
        elif has_critical and risk_level == "medium":
            risk_level = "high"

        # Generate comment
        comment_lines = [
            "## 🔍 Impact Analysis",
            "",
            f"**Changed Files:** {changed_count}",
            f"**Impacted Files:** {total_impacted}",
            f"**Risk Level:** {risk_level.title()}",
            "",
            "### 📋 Details",
        ]

        if direct_impacted:
            comment_lines.append(f"- **Direct impact:** {', '.join(sorted(direct_impacted))}")

        if transitive_impacted:
            comment_lines.append(f"- **Transitive impact:** {', '.join(sorted(transitive_impacted))}")

        if test_impacted:
            comment_lines.append(f"- **Test impact:** {', '.join(sorted(test_impacted))}")

        comment_lines.extend([
            "",
            "### 💡 Recommendations"
        ])

        if risk_level == "high":
            comment_lines.extend([
                "- ⚠️ **High risk changes** - Requires thorough review",
                "- 🔬 Run comprehensive test suite",
                "- 👥 Consider pair programming for critical changes"
            ])
        elif risk_level == "medium":
            comment_lines.extend([
                "- 📝 Review API changes carefully",
                "- 🧪 Run full test suite",
                "- 🔍 Check for breaking changes"
            ])
        else:
            comment_lines.extend([
                "- ✅ Low risk changes",
                "- 🧪 Run relevant tests",
                "- 📖 Update documentation if needed"
            ])

        if has_critical:
            comment_lines.append("- 🚨 Critical system files impacted - extra caution required")

        comment = "\n".join(comment_lines)

        return PRImpactResponse(
            impacted_files=sorted(list(all_impacted)),
            risk_level=risk_level,
            comment=comment
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PR impact analysis failed: {str(e)}")