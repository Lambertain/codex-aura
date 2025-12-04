# Claude Integration Guide

This guide shows how to integrate Codex Aura with Anthropic's Claude for enhanced code analysis and bug fixing.

## Setup

First, install required dependencies:

```bash
pip install codex-aura anthropic
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Basic Integration

### Bug Fixing with Context

```python
import os
from pathlib import Path
from anthropic import Anthropic
from codex_aura import CodexAura

def fix_bug_with_claude(
    repo_path: str,
    bug_description: str,
    file_hint: Optional[str] = None
) -> str:
    """Fix a bug using Claude with Codex Aura context."""

    # Initialize Codex Aura
    ca = CodexAura(repo_path=repo_path)

    # Get context around the bug
    context = ca.get_context(
        task=bug_description,
        entry_points=[file_hint] if file_hint else None,
        max_tokens=6000
    )

    # Initialize Anthropic client
    anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Build prompt
    prompt = f"""You are a senior developer fixing a bug.

## Bug Description
{bug_description}

## Relevant Code Context
{context.to_prompt(format="markdown")}

## Instructions
1. Analyze the code and identify the bug
2. Provide a fix with explanation
3. Suggest tests to prevent regression

Respond with the fix."""

    # Call Claude
    response = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text
```

### Usage Example

```python
# Fix a login validation bug
bug_description = "Login returns wrong error code for invalid credentials"
file_hint = "src/auth/login.py"

fix = fix_bug_with_claude(
    repo_path="./my_project",
    bug_description=bug_description,
    file_hint=file_hint
)

print("Claude's fix:")
print(fix)
```

## Advanced Integration

### XML Context Format

For complex codebases, XML format can provide better structure:

```python
def fix_bug_with_claude_xml(
    repo_path: str,
    bug_description: str,
    file_hint: Optional[str] = None
) -> str:
    """Fix a bug using Claude with XML-formatted context."""

    # Initialize Codex Aura
    ca = CodexAura(repo_path=repo_path)

    # Get context
    context = ca.get_context(
        task=bug_description,
        entry_points=[file_hint] if file_hint else None,
        max_tokens=6000
    )

    # Initialize Anthropic client
    anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Build prompt with XML context
    prompt = f"""You are a senior developer fixing a bug.

## Bug Description
{bug_description}

## Code Context (XML)
{context.to_prompt(format="xml", include_edges=True)}

## Instructions
1. Analyze the XML context and identify the bug
2. Provide a fix with explanation
3. Suggest tests to prevent regression

Respond with the fix."""

    # Call Claude
    response = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text
```

## Code Review Integration

```python
def code_review_with_claude(repo_path: str, pr_files: List[str]) -> str:
    """Perform code review using Claude with Codex Aura context."""

    # Initialize Codex Aura
    ca = CodexAura(repo_path=repo_path)

    # Get impact of changed files
    impact = ca.analyze_impact(pr_files)

    # Get context for affected area
    context = ca.get_context(
        task="Code review for changes",
        entry_points=pr_files,
        depth=1,
        max_tokens=4000
    )

    # Initialize Anthropic client
    anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Review these code changes.

Changed files: {pr_files}
Affected files: {[f['path'] for f in impact.affected_files]}

Context:
{context.to_prompt()}

Provide:
1. Potential issues
2. Suggestions for improvement
3. Security concerns if any"""

    response = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].message
```

## Best Practices

### Context Optimization

1. **Use specific entry points**: Provide targeted file hints to focus context
2. **Adjust depth**: Use depth=1 for reviews, depth=2-3 for complex fixes
3. **Token limits**: Set appropriate max_tokens based on your Claude plan
4. **Format selection**: Use markdown for readability, XML for complex relationships

### Error Handling

```python
try:
    context = ca.get_context(task=task, entry_points=files)
    # Use context...
except Exception as e:
    print(f"Context retrieval failed: {e}")
    # Fallback to basic approach
```

### Performance Tips

- Cache analysis results for repeated operations
- Use remote mode for large repositories
- Pre-analyze repositories during off-peak hours
- Monitor token usage and adjust limits accordingly

## Troubleshooting

### Common Issues

**Context too large**: Reduce max_tokens or use more specific entry points

**Missing files**: Ensure entry point files exist and are properly analyzed

**Empty context**: Check that the repository has been analyzed first with `ca.analyze()`

**API errors**: Verify ANTHROPIC_API_KEY is set correctly

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will show Codex Aura analysis progress and API calls.

## Complete Example

See `examples/agents/claude_agent.py` for a complete working example with both markdown and XML context formats.