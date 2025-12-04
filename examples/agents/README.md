# Claude Agent Integration

This directory contains examples of integrating Codex Aura with Claude for automated code analysis and bug fixing.

## Prerequisites

1. **Anthropic API Key**: Set the `ANTHROPIC_API_KEY` environment variable
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

2. **Codex Aura**: Install the codex-aura package
   ```bash
   pip install codex-aura
   ```

3. **Anthropic SDK**: Install the Anthropic Python SDK
   ```bash
   pip install anthropic
   ```

## Examples

### Basic Bug Fixing

The `claude_agent.py` script demonstrates how to use Codex Aura to provide context to Claude for bug fixing:

```python
from codex_aura import CodexAura
from anthropic import Anthropic

# Initialize clients
ca = CodexAura(repo_path=".")
anthropic = Anthropic()

# Get context
context = ca.get_context(
    task="JWT tokens are not validated correctly",
    entry_points=["src/auth/jwt.py"],
    max_tokens=6000
)

# Format context for Claude
prompt_context = context.to_prompt(format="markdown")

# Build prompt and call Claude
# ... (see claude_agent.py for full example)
```

## Context Formats

Codex Aura supports multiple output formats optimized for different LLMs:

### Markdown (Default)
Best for Claude and other markdown-aware models:
```python
context.to_prompt(format="markdown", include_tree=True, include_edges=True)
```

### XML
Structured format ideal for Claude's XML processing capabilities:
```python
context.to_prompt(format="xml", include_edges=True)
```

### Plain Text
Simple text format for basic models:
```python
context.to_prompt(format="plain")
```

## Token Savings

Using Codex Aura with Claude can save significant tokens compared to sending entire files:

- **Without Codex Aura**: Send entire codebase (~50k+ tokens)
- **With Codex Aura**: Send only relevant context (~2k-6k tokens)
- **Savings**: Up to 90% token reduction

## Running the Examples

1. Set your Anthropic API key:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

2. Run the example:
   ```bash
   cd examples/agents
   python claude_agent.py
   ```

## Configuration Options

### Context Parameters
- `task`: Description of the work to be done
- `entry_points`: List of files/classes/functions to focus on
- `max_tokens`: Maximum context size (affects node selection)

### Formatting Options
- `format`: Output format ("plain", "markdown", "xml")
- `include_tree`: Include file structure overview
- `include_edges`: Include dependency relationships
- `max_chars`: Truncate output to specified character limit

## Best Practices

1. **Be Specific**: Provide detailed bug descriptions
2. **Use Entry Points**: Specify relevant files when possible
3. **Choose Format Wisely**: Use XML for Claude, Markdown for others
4. **Set Token Limits**: Balance context richness with API costs
5. **Include Dependencies**: Use `include_edges=True` for complex fixes

## Troubleshooting

### Common Issues

1. **No context found**: Ensure the repository has been analyzed with `CodexAura.analyze()`
2. **API Key errors**: Verify `ANTHROPIC_API_KEY` is set correctly
3. **Empty responses**: Check that entry points exist in the codebase

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)