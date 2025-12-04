# Best Practices for Codex Aura SDK

This guide covers optimization techniques, performance tips, and recommended patterns for using Codex Aura effectively.

## Performance Optimization

### Context Size Management

**Token Limits**: Always set appropriate `max_tokens` based on your LLM provider:

```python
# For GPT-3.5-turbo (4K context)
context = ca.get_context(task=task, entry_points=files, max_tokens=3000)

# For GPT-4/Claude (8K+ context)
context = ca.get_context(task=task, entry_points=files, max_tokens=6000)

# For large contexts (32K+ models)
context = ca.get_context(task=task, entry_points=files, max_tokens=25000)
```

**Depth Control**: Adjust traversal depth based on task complexity:

```python
# Simple bug fixes
context = ca.get_context(task=task, entry_points=files, depth=1)

# Complex feature development
context = ca.get_context(task=task, entry_points=files, depth=3)
```

### Caching Strategies

**Graph Caching**: Reuse analyzed graphs for multiple operations:

```python
# Analyze once
graph_id = ca.analyze()

# Reuse for multiple contexts
context1 = ca.get_context(task="Fix bug", entry_points=["file1.py"], graph_id=graph_id)
context2 = ca.get_context(task="Add feature", entry_points=["file2.py"], graph_id=graph_id)
```

**Context Caching**: Cache frequently used contexts:

```python
import pickle
from pathlib import Path

def get_cached_context(ca, task, files, cache_dir="./.codex_cache"):
    """Get context with caching."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(exist_ok=True)

    # Create cache key
    cache_key = f"{hash(task + str(files))}.pkl"
    cache_file = cache_dir / cache_key

    if cache_file.exists():
        with open(cache_file, 'rb') as f:
            return pickle.load(f)

    # Generate context
    context = ca.get_context(task=task, entry_points=files)

    # Cache it
    with open(cache_file, 'wb') as f:
        pickle.dump(context, f)

    return context
```

## Entry Point Selection

### Choosing Entry Points

**For Bug Fixes**: Use the file containing the bug:

```python
# Direct approach
context = ca.get_context(
    task="Fix null pointer in login",
    entry_points=["src/auth/login.py"]
)
```

**For Feature Development**: Include related files:

```python
# Multiple entry points
context = ca.get_context(
    task="Add user registration API",
    entry_points=[
        "src/api/routes.py",
        "src/auth/user.py",
        "src/models/user.py"
    ]
)
```

**For Code Reviews**: Use changed files:

```python
# PR files as entry points
pr_files = ["src/auth/login.py", "src/auth/session.py"]
context = ca.get_context(
    task="Review authentication changes",
    entry_points=pr_files
)
```

## Error Handling

### Robust Integration

```python
def safe_get_context(ca, task, entry_points, **kwargs):
    """Get context with error handling."""
    try:
        return ca.get_context(task=task, entry_points=entry_points, **kwargs)
    except ValidationError as e:
        print(f"Validation error: {e}")
        # Try with broader entry points
        return ca.get_context(task=task, entry_points=[], **kwargs)
    except AnalysisError as e:
        print(f"Analysis error: {e}")
        # Fallback to basic context
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
```

### Graceful Degradation

```python
def get_context_with_fallback(ca, task, files):
    """Get context with fallback options."""
    # Try Codex Aura first
    try:
        return ca.get_context(task=task, entry_points=files)
    except Exception:
        pass

    # Fallback: basic file reading
    context_parts = []
    for file in files[:3]:  # Limit to 3 files
        try:
            with open(file, 'r') as f:
                content = f.read()[:2000]  # Limit content
                context_parts.append(f"## {file}\n```\n{content}\n```")
        except Exception:
            continue

    return "\n".join(context_parts)
```

## Context Formatting

### Format Selection

**Markdown**: Best for readability and most LLMs:

```python
prompt = context.to_prompt(format="markdown", include_tree=True)
```

**XML**: Better for structured analysis:

```python
prompt = context.to_prompt(format="xml", include_edges=True)
```

**Plain Text**: For simple integrations:

```python
prompt = context.to_prompt(format="plain")
```

### Custom Formatting

```python
def custom_format_context(context):
    """Custom context formatting."""
    lines = ["# Custom Context Format\n"]

    for node in context.context_nodes:
        lines.append(f"## {node.path}")
        lines.append(f"Type: {node.type}")
        if node.code:
            lines.append(f"```python\n{node.code}\n```")
        lines.append("")

    return "\n".join(lines)
```

## Impact Analysis Integration

### Pre-Change Analysis

```python
def analyze_change_impact(ca, changed_files):
    """Analyze impact before making changes."""
    impact = ca.analyze_impact(changed_files)

    print(f"Files to review: {len(impact.affected_files)}")
    print(f"Tests to run: {len(impact.affected_tests)}")

    # Get focused context
    context = ca.get_context(
        task="Review changes",
        entry_points=changed_files,
        depth=2
    )

    return impact, context
```

### Test Impact Assessment

```python
def get_test_scope(ca, changed_files):
    """Determine which tests to run."""
    impact = ca.analyze_impact(changed_files)

    test_files = impact.affected_tests

    # Add unit tests for changed files
    for changed_file in changed_files:
        test_file = changed_file.replace('.py', '_test.py')
        if Path(test_file).exists():
            test_files.append(test_file)

    return list(set(test_files))  # Remove duplicates
```

## Remote vs Local Mode

### When to Use Remote Mode

```python
# Large repositories
ca = CodexAura(server_url="https://api.codex-aura.com")

# Team collaboration
# Multiple developers can share analyzed graphs

# CI/CD integration
# Pre-analyzed graphs for faster feedback
```

### When to Use Local Mode

```python
# Small projects
ca = CodexAura(repo_path="./my_project")

# Development environment
# No external dependencies

# Custom analysis needs
# Full control over analysis process
```

## Monitoring and Metrics

### Token Usage Tracking

```python
import tiktoken

def track_token_usage(context, response):
    """Track token usage for cost monitoring."""
    enc = tiktoken.get_encoding("cl100k_base")

    context_tokens = len(enc.encode(str(context)))
    response_tokens = len(enc.encode(response))

    print(f"Context tokens: {context_tokens}")
    print(f"Response tokens: {response_tokens}")
    print(f"Total tokens: {context_tokens + response_tokens}")

    return {
        "context_tokens": context_tokens,
        "response_tokens": response_tokens,
        "total_tokens": context_tokens + response_tokens
    }
```

### Performance Monitoring

```python
import time

def benchmark_operation(operation, *args, **kwargs):
    """Benchmark Codex Aura operations."""
    start_time = time.time()
    result = operation(*args, **kwargs)
    duration = time.time() - start_time

    print(f"Operation took {duration:.2f}s")
    return result, duration
```

## Security Considerations

### Input Validation

```python
def validate_entry_points(entry_points):
    """Validate entry points for security."""
    allowed_extensions = {'.py', '.js', '.ts', '.java'}

    for path in entry_points:
        if not Path(path).exists():
            raise ValueError(f"File does not exist: {path}")

        if Path(path).suffix not in allowed_extensions:
            raise ValueError(f"Unsupported file type: {path}")

        # Check for path traversal
        resolved = Path(path).resolve()
        if not str(resolved).startswith(str(Path.cwd())):
            raise ValueError(f"Path outside working directory: {path}")

    return entry_points
```

### Sensitive Data Handling

```python
def sanitize_context(context):
    """Remove sensitive data from context."""
    # Remove API keys, passwords, etc.
    sanitized = str(context)

    # Simple pattern-based sanitization
    import re
    patterns = [
        r'API_KEY\s*=\s*["\'][^"\']*["\']',
        r'PASSWORD\s*=\s*["\'][^"\']*["\']',
        r'SECRET\s*=\s*["\'][^"\']*["\']'
    ]

    for pattern in patterns:
        sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)

    return sanitized
```

## Troubleshooting

### Common Performance Issues

**Slow Analysis**: Use remote mode or pre-analyze repositories

**Large Contexts**: Reduce depth, use specific entry points, set token limits

**Memory Usage**: Process large repositories in chunks

### Debug Techniques

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Profile operations
import cProfile
cProfile.run('ca.analyze()')

# Check graph size
graphs = ca.list_graphs()
for graph in graphs:
    print(f"Graph {graph['id']}: {graph.get('node_count', 'unknown')} nodes")
```

## Integration Patterns

### CLI Tool Integration

```python
def create_codex_command():
    """Integrate Codex Aura into CLI workflow."""
    import click

    @click.command()
    @click.argument('task')
    @click.option('--files', multiple=True)
    @click.option('--depth', default=2)
    def codex_analyze(task, files, depth):
        ca = CodexAura(repo_path=".")
        context = ca.get_context(task=task, entry_points=list(files), depth=depth)
        print(context.to_prompt())

    return codex_analyze
```

### IDE Plugin Integration

```python
class CodexAuraPlugin:
    """Example IDE plugin integration."""

    def __init__(self):
        self.ca = CodexAura(repo_path=self.get_project_root())

    def on_file_open(self, file_path):
        """Provide context when file is opened."""
        context = self.ca.get_context(
            task=f"Understanding {file_path}",
            entry_points=[file_path]
        )
        self.show_context_popup(context)

    def on_code_selection(self, file_path, start_line, end_line):
        """Provide context for selected code."""
        # Implementation for code selection context
        pass
```

## Migration Guide

### Upgrading from Direct File Reading

```python
# Old approach
def get_file_context(file_path):
    with open(file_path, 'r') as f:
        return f.read()

# New approach with Codex Aura
def get_smart_context(ca, file_path, task):
    return ca.get_context(task=task, entry_points=[file_path])
```

### Batch Processing

```python
def process_multiple_tasks(ca, tasks):
    """Process multiple tasks efficiently."""
    # Analyze once
    graph_id = ca.analyze()

    results = []
    for task in tasks:
        context = ca.get_context(
            task=task['description'],
            entry_points=task['files'],
            graph_id=graph_id
        )
        results.append(context)

    return results
```

This guide covers the most important patterns and techniques for effective Codex Aura usage. Regular updates and community contributions help improve these best practices over time.