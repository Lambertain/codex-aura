# Codex Aura

Interactive code dependency visualization and analysis tool for VS Code.

## Features

- **📊 Graph Visualization**: Interactive graph view of code dependencies and relationships
- **🔍 Node Details**: Detailed information panel for selected nodes
- **⚡ Workspace Analysis**: Analyze entire workspaces for code insights
- **🎯 Status Bar Integration**: Real-time server connection status
- **🎨 D3.js Integration**: Smooth, interactive visualizations with zoom and pan

## Installation

Install from the [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=codex-aura.codex-aura) or search for "Codex Aura" in the Extensions view.

## Requirements

- VS Code 1.85.0 or higher
- Codex Aura server running (default: http://localhost:8000)

## Configuration

Configure the Codex Aura server URL in VS Code settings:

1. Open VS Code Settings (`Ctrl+,`)
2. Search for "Codex Aura"
3. Set the server URL in `Codex Aura: Server Url`

```json
{
  "codexAura.serverUrl": "http://localhost:8000"
}
```

## Usage

### Basic Usage

1. **Open Command Palette** (`Ctrl+Shift+P`)
2. **Run "Codex Aura: Analyze Workspace"** to analyze your codebase
3. **Run "Codex Aura: Show Code Graph"** to visualize the dependency graph

### Status Bar

The status bar shows the connection status:
- $(database) **Codex Aura: Ready** - Server is connected
- $(warning) **Codex Aura: Not Connected** - Server is unavailable
- $(sync~spin) **Analyzing...** - Analysis in progress

Click the status bar item to open settings.

### Graph Navigation

- **Zoom**: Mouse wheel or pinch gestures
- **Pan**: Click and drag
- **Select Nodes**: Click on nodes to view details
- **Dependencies**: Right-click files in Explorer to show dependencies

## Commands

- `Codex Aura: Show Code Graph` - Display the code dependency graph
- `Codex Aura: Analyze Workspace` - Analyze the current workspace
- `Codex Aura: Show Dependencies` - Show dependencies for selected file
- `Codex Aura: Show Function Dependencies` - Show dependencies for current function
- `Codex Aura: Open Settings` - Open extension settings

## Troubleshooting

### Server Connection Issues

1. Ensure the Codex Aura server is running
2. Check the server URL in settings
3. Verify network connectivity

### Analysis Fails

1. Check that you have a workspace folder open
2. Ensure the server can access your project files
3. Check VS Code output panel for error messages

## Contributing

We welcome contributions! Please see our [contributing guide](https://github.com/Lambertain/codex-aura/blob/master/CONTRIBUTING.md) for details.

## License

MIT License - see [LICENSE](https://github.com/Lambertain/codex-aura/blob/master/LICENSE) file for details

## Support

- [GitHub Issues](https://github.com/Lambertain/codex-aura/issues)
- [Documentation](https://github.com/Lambertain/codex-aura#readme)