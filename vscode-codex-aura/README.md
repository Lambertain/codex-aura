# Codex Aura VS Code Extension

A VS Code extension for visualizing code context graphs using Codex Aura API.

## Features

- **Graph Visualization**: Interactive graph view of code dependencies and relationships
- **Node Details**: Detailed information panel for selected nodes
- **Workspace Analysis**: Analyze entire workspaces for code insights
- **D3.js Integration**: Smooth, interactive visualizations with zoom and pan

## Installation

1. Clone the repository
2. Run `npm install` to install dependencies
3. Run `npm run compile` to build the extension
4. Open VS Code and go to Extensions > Install from VSIX
5. Select the generated `.vsix` file

## Configuration

Configure the Codex Aura server URL in VS Code settings:

```json
{
  "codexAura.serverUrl": "http://localhost:8000"
}
```

## Usage

1. Open Command Palette (`Ctrl+Shift+P`)
2. Run `Codex Aura: Show Code Graph` to visualize graphs
3. Run `Codex Aura: Analyze Workspace` to analyze the current workspace

## Development

### Prerequisites

- Node.js 18+
- VS Code

### Building

```bash
npm install
npm run compile
```

### Testing

```bash
npm run test
```

### Debugging

1. Open the project in VS Code
2. Press F5 to launch extension development host
3. Test the extension in the new window

## API Integration

The extension communicates with Codex Aura API endpoints:

- `GET /api/v1/graphs` - List available graphs
- `GET /api/v1/graph/{id}` - Get specific graph
- `GET /api/v1/graph/{id}/node/{nodeId}` - Get node details
- `GET /api/v1/graph/{id}/node/{nodeId}/dependencies` - Get node dependencies

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details