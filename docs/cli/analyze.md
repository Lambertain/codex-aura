# Analyze Command

The `analyze` command performs code analysis and generates dependency graphs.

## Usage

```bash
codex-aura analyze [OPTIONS] [PATH]
```

## Arguments

- `PATH`: Path to analyze (default: current directory)

## Options

- `-o, --output TEXT`: Output file path (default: codex-aura-graph.json)
- `--edge-types TEXT`: Comma-separated edge types (default: imports,calls,extends)
- `--exclude-patterns TEXT`: Patterns to exclude
- `--include-patterns TEXT`: Patterns to include
- `--config FILE`: Configuration file path
- `--verbose`: Enable verbose output

## Examples

Basic analysis:

```bash
codex-aura analyze .
```

Analyze specific directory with custom output:

```bash
codex-aura analyze src/ -o my-graph.json
```

Analyze with specific edge types:

```bash
codex-aura analyze . --edge-types imports,calls
```

Exclude test files:

```bash
codex-aura analyze . --exclude-patterns "test_*"
```

## Output

The command generates a JSON file containing:

- **nodes**: Code entities (modules, classes, functions)
- **edges**: Relationships between entities
- **metadata**: Analysis information and statistics

## Edge Types

- `imports`: Module import relationships
- `calls`: Function/method call relationships
- `extends`: Class inheritance relationships
- `contains`: Structural containment relationships