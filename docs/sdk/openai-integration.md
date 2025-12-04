# OpenAI Integration Guide

This guide shows how to integrate Codex Aura with OpenAI's GPT models for enhanced code analysis and development tasks.

## Setup

First, install required dependencies:

```bash
pip install codex-aura openai
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Basic Integration

### Code Review with GPT

```python
import os
from typing import List
from openai import OpenAI
from codex_aura import CodexAura

def code_review_with_gpt(repo_path: str, pr_files: List[str]) -> str:
    """Perform code review using GPT with Codex Aura context."""

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

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""Review these code changes.

Changed files: {pr_files}
Affected files: {[f['path'] for f in impact.affected_files]}

Context:
{context.to_prompt()}

Provide:
1. Potential issues
2. Suggestions for improvement
3. Security concerns if any"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
```

### Usage Example

```python
# Review pull request changes
pr_files = ["src/auth/login.py", "tests/test_auth.py"]

review = code_review_with_gpt(
    repo_path="./my_project",
    pr_files=pr_files
)

print("GPT's code review:")
print(review)
```

## Advanced Integration

### Feature Development Assistant

```python
def implement_feature_with_gpt(
    repo_path: str,
    feature_description: str,
    entry_files: List[str]
) -> str:
    """Implement a feature using GPT with Codex Aura context."""

    # Initialize Codex Aura
    ca = CodexAura(repo_path=repo_path)

    # Get context for relevant files
    context = ca.get_context(
        task=f"Implement feature: {feature_description}",
        entry_points=entry_files,
        depth=2,
        max_tokens=6000
    )

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""Implement this feature in the codebase.

## Feature Description
{feature_description}

## Relevant Code Context
{context.to_prompt(format="markdown", include_edges=True)}

## Requirements
1. Implement the feature following existing code patterns
2. Add appropriate error handling
3. Include docstrings and comments
4. Suggest unit tests

Provide the implementation with file paths and code changes."""

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000
    )

    return response.choices[0].message.content
```

### Bug Analysis and Fixing

```python
def analyze_bug_with_gpt(
    repo_path: str,
    bug_description: str,
    affected_files: List[str]
) -> str:
    """Analyze and suggest fix for a bug using GPT with context."""

    # Initialize Codex Aura
    ca = CodexAura(repo_path=repo_path)

    # Get comprehensive context
    context = ca.get_context(
        task=f"Analyze bug: {bug_description}",
        entry_points=affected_files,
        depth=3,
        max_tokens=8000
    )

    # Get impact analysis
    impact = ca.analyze_impact(affected_files)

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""Analyze this bug and suggest a fix.

## Bug Description
{bug_description}

## Affected Files
{affected_files}

## Impact Analysis
- Affected files: {len(impact.affected_files)}
- Affected tests: {len(impact.affected_tests)}

## Code Context
{context.to_prompt()}

## Analysis Request
1. Root cause analysis
2. Suggested fix with code changes
3. Potential side effects
4. Test cases to verify the fix"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000
    )

    return response.choices[0].message.content
```

## Model Selection

### GPT-4 vs GPT-3.5-turbo

- **GPT-4**: Better for complex analysis, code generation, and detailed explanations
- **GPT-3.5-turbo**: Faster and more cost-effective for simpler tasks

```python
# For complex code analysis
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=4000
)

# For quick reviews
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=2000
)
```

## Best Practices

### Context Optimization

1. **Entry points**: Choose the most relevant files as entry points
2. **Depth control**: Use depth=1 for focused tasks, depth=2-3 for complex analysis
3. **Token management**: Monitor usage and adjust max_tokens accordingly
4. **Format selection**: Markdown works well for most GPT interactions

### Error Handling

```python
try:
    context = ca.get_context(task=task, entry_points=files)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
except Exception as e:
    print(f"Error: {e}")
    # Fallback logic
```

### Cost Optimization

- Use GPT-3.5-turbo for routine tasks
- Cache context results to avoid repeated analysis
- Set appropriate max_tokens to control costs
- Batch related operations when possible

## Streaming Responses

For long responses, use streaming:

```python
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## Troubleshooting

### Common Issues

**Rate limits**: Implement exponential backoff retry logic

**Token limits**: Reduce context size or use GPT-4-32k

**Context too large**: Use more specific entry points or reduce depth

**API errors**: Check API key and account status

### Debug Tips

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Monitor token usage:

```python
# Check token usage in response
usage = response.usage
print(f"Prompt tokens: {usage.prompt_tokens}")
print(f"Completion tokens: {usage.completion_tokens}")
print(f"Total tokens: {usage.total_tokens}")
```

## Complete Example

See `examples/agents/openai_agent.py` for a complete working example of code review integration.