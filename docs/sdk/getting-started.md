# Getting Started with Codex Aura SDK

## Overview

Codex Aura SDK provides a Python interface for analyzing code repositories and generating contextual information for AI agents. It supports both local analysis and remote server connections.

## Installation

Install Codex Aura SDK using pip:

```bash
pip install codex-aura
```

Or from source:

```bash
git clone https://github.com/your-org/codex-aura.git
cd codex-aura
pip install -e .
```

## Quick Start

### Local Mode

```python
from codex_aura import CodexAura

# Initialize with local repository
ca = CodexAura(repo_path="/path/to/your/project")

# Analyze the repository
graph_id = ca.analyze()

# Get context for a task
context = ca.get_context(
    task="Fix login validation bug",
    entry_points=["src/auth/login.py"]
)

# Format context as prompt
prompt = context.to_prompt(format="markdown")
print(prompt)
```

### Remote Mode

```python
from codex_aura import CodexAura

# Connect to remote server
ca = CodexAura(server_url="http://localhost:8000")

# Use the same API
graph_id = ca.analyze(repo_path="/path/to/project")
context = ca.get_context(
    task="Add user registration",
    entry_points=["src/auth/register.py"]
)
```

## Basic Concepts

### Repository Analysis

Codex Aura analyzes Python code to build a dependency graph that understands:
- Function and class definitions
- Import relationships
- Function calls
- Inheritance hierarchies

### Context Generation

Context provides relevant code snippets and relationships for specific tasks, significantly reducing token usage compared to providing entire repositories.

### Impact Analysis

Analyze which files are affected by changes to understand testing and review scope.

## Next Steps

- [API Reference](api-reference.md) - Complete SDK documentation
- [Claude Integration](claude-integration.md) - Using with Anthropic Claude
- [OpenAI Integration](openai-integration.md) - Using with OpenAI GPT
- [Best Practices](best-practices.md) - Optimization and usage tips