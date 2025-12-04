# VS Code Extension

The Codex Aura VS Code extension provides integrated code analysis directly in your editor.

## Installation

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "Codex Aura"
4. Click Install

## Features

### Dependency Graph Visualization

- View dependency graphs directly in VS Code
- Interactive graph exploration
- Click nodes to navigate to code

### Code Analysis

- Real-time analysis as you code
- Highlight dependencies and relationships
- Show complexity metrics

### Commands

- `Codex Aura: Analyze Current File` - Analyze the active file
- `Codex Aura: Analyze Workspace` - Analyze entire workspace
- `Codex Aura: Show Graph` - Display dependency graph
- `Codex Aura: Export Graph` - Export graph to JSON

## Configuration

Configure the extension in VS Code settings:

```json
{
  "codexAura.analyzer.path": "python",
  "codexAura.graph.layout": "force",
  "codexAura.analysis.autoUpdate": true
}
```

## Usage

1. Open a Python project
2. Run "Codex Aura: Analyze Workspace" from command palette
3. View the graph in the Codex Aura panel
4. Click on nodes to navigate to code locations

## Requirements

- Python 3.11+
- Codex Aura package installed
- VS Code 1.70+