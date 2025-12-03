# Codex Aura

Code context mapping for AI agents - analyze Python import relationships and dependencies.

## Installation

```bash
pip install -e .
```

## Quick Start

Analyze a Python repository:

```bash
# Analyze repository and save graph
python -m codex_aura.cli.main analyze /path/to/repo -o graph.json

# Show graph statistics
python -m codex_aura.cli.main stats graph.json
```

## Demo: Impact Analysis

See which files are affected when you change a source file:

```bash
# First, analyze the repository
python -m codex_aura.cli.main analyze examples/simple_project -o graph.json

# Show impact of changing utils.py
python examples/demo_affected.py graph.json src/utils.py
```

Output:
```
🎯 Analyzing impact of changes to: src/utils.py

📥 Files that IMPORT this file (will be affected):
   • src/services/user.py (line 1)
   • src/main.py (line 1)

📤 Files that this file IMPORTS (dependencies):
   • src/config.py (line 1)

🔄 Total impact: 3 files
```

## Demo: Graph Visualization

Visualize import relationships as an ASCII tree:

```bash
# Visualize imports starting from main.py
python examples/demo_visualize.py graph.json src/main.py --depth 2
```

Output:
```
src/main.py
├── imports: src/utils.py
│   └── imports: src/config.py
├── imports: src/services/user.py
│   ├── imports: src/utils.py
│   └── imports: src/services/models/user.py
```

## Demo: Graph Stats

Show detailed statistics about the analyzed codebase:

```bash
python -m codex_aura.cli.main stats graph.json
```

## Benchmark Results

Measure performance on real repositories:

```bash
# Benchmark on a large repository
python examples/benchmark.py /path/to/large/repo
```

Example output:
```
Benchmark: flask (127 files, 45K LOC)
  Scan files:    0.05s
  Parse AST:     0.82s
  Build graph:   0.15s
  Total:         1.02s

Performance: 44K LOC/sec
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

Licensed under the Apache License, Version 2.0.