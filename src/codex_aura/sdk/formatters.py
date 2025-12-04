"""Formatters for Codex Aura SDK output."""

from typing import List, Dict, Any, Optional
from .context import ContextNode, Context
from .impact import AffectedFile, ImpactAnalysis


class PromptFormatter:
    """Base class for prompt formatters."""

    def format_context(self, context: Context, **kwargs) -> str:
        """Format context for prompts."""
        raise NotImplementedError

    def format_impact(self, impact: ImpactAnalysis, **kwargs) -> str:
        """Format impact analysis for prompts."""
        raise NotImplementedError


class MarkdownFormatter(PromptFormatter):
    """Markdown formatter for prompts."""

    def format_context(self, context: Context, include_tree: bool = False) -> str:
        """Format context as markdown."""
        return context._to_markdown_prompt(include_tree)

    def format_impact(self, impact: ImpactAnalysis, include_summary: bool = True) -> str:
        """Format impact analysis as markdown."""
        lines = ["# Impact Analysis\n"]

        lines.append("## Changed Files\n")
        for file in impact.changed_files:
            lines.append(f"- {file}")
        lines.append("")

        lines.append("## Affected Files\n")
        for affected in impact.affected_files:
            lines.append(f"- **{affected.path}** ({affected.impact_type})")
            if affected.edges:
                lines.append(f"  - Edges: {', '.join(affected.edges)}")
            if affected.distance is not None:
                lines.append(f"  - Distance: {affected.distance}")
        lines.append("")

        lines.append("## Suggested Tests\n")
        for test in impact.affected_tests:
            lines.append(f"- {test}")
        lines.append("")

        if include_summary:
            lines.append("## Summary\n")
            summary = impact.to_dict()["summary"]
            lines.append(f"- Total affected files: {summary['total_affected_files']}")
            lines.append(f"- Direct impact: {summary['direct_affected_files']}")
            lines.append(f"- Transitive impact: {summary['transitive_affected_files']}")
            lines.append(f"- Affected tests: {summary['affected_tests']}")
            lines.append(f"- Max transitive distance: {summary['max_transitive_distance']}")

        return "\n".join(lines)


class TextFormatter(PromptFormatter):
    """Plain text formatter for prompts."""

    def format_context(self, context: Context, include_tree: bool = False) -> str:
        """Format context as plain text."""
        return context._to_text_prompt(include_tree)

    def format_impact(self, impact: ImpactAnalysis, include_summary: bool = True) -> str:
        """Format impact analysis as plain text."""
        lines = ["IMPACT ANALYSIS\n"]

        lines.append("CHANGED FILES:")
        for file in impact.changed_files:
            lines.append(f"  {file}")
        lines.append("")

        lines.append("AFFECTED FILES:")
        for affected in impact.affected_files:
            lines.append(f"  {affected.path} ({affected.impact_type})")
            if affected.edges:
                lines.append(f"    Edges: {', '.join(affected.edges)}")
            if affected.distance is not None:
                lines.append(f"    Distance: {affected.distance}")
        lines.append("")

        lines.append("SUGGESTED TESTS:")
        for test in impact.affected_tests:
            lines.append(f"  {test}")
        lines.append("")

        if include_summary:
            lines.append("SUMMARY:")
            summary = impact.to_dict()["summary"]
            lines.append(f"  Total affected files: {summary['total_affected_files']}")
            lines.append(f"  Direct impact: {summary['direct_affected_files']}")
            lines.append(f"  Transitive impact: {summary['transitive_affected_files']}")
            lines.append(f"  Affected tests: {summary['affected_tests']}")
            lines.append(f"  Max transitive distance: {summary['max_transitive_distance']}")

        return "\n".join(lines)


class JSONFormatter(PromptFormatter):
    """JSON formatter for prompts."""

    def format_context(self, context: Context, **kwargs) -> str:
        """Format context as JSON."""
        return context._to_json_prompt()

    def format_impact(self, impact: ImpactAnalysis, **kwargs) -> str:
        """Format impact analysis as JSON."""
        import json
        return json.dumps(impact.to_dict(), indent=2)


# Default formatters
markdown_formatter = MarkdownFormatter()
text_formatter = TextFormatter()
json_formatter = JSONFormatter()

FORMATTERS = {
    "markdown": markdown_formatter,
    "text": text_formatter,
    "json": json_formatter,
}


def get_formatter(format_type: str) -> PromptFormatter:
    """Get formatter by type."""
    if format_type not in FORMATTERS:
        raise ValueError(f"Unknown formatter type: {format_type}. Available: {list(FORMATTERS.keys())}")
    return FORMATTERS[format_type]