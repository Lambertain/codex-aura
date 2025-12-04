import * as vscode from 'vscode';
import { CodexAuraClient } from '../api/client';

export function registerCommands(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration('codexAura');
  const serverUrl = config.get<string>('serverUrl', 'http://localhost:8000');
  const client = new CodexAuraClient(serverUrl);

  // Command to show graph
  const showGraphCommand = vscode.commands.registerCommand('codexAura.showGraph', async () => {
    try {
      const graphs = await client.getGraphs();

      if (graphs.length === 0) {
        vscode.window.showInformationMessage('No graphs available');
        return;
      }

      const graphItems = graphs.map(graph => ({
        label: graph.name,
        description: `ID: ${graph.id}`,
        graph: graph
      }));

      const selectedGraph = await vscode.window.showQuickPick(graphItems, {
        placeHolder: 'Select a graph to visualize'
      });

      if (selectedGraph) {
        // Open the graph view
        await vscode.commands.executeCommand('workbench.view.extension.codexAura-graph');
        // Send message to load the graph
        // This would need to be handled by the view provider
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to load graphs: ${error}`);
    }
  });

  // Command to analyze workspace
  const analyzeCommand = vscode.commands.registerCommand('codexAura.analyze', async () => {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showErrorMessage('No workspace folder open');
      return;
    }

    vscode.window.showInformationMessage('Analyzing workspace...');

    try {
      // This would call the analysis API
      // For now, just show a placeholder
      vscode.window.showInformationMessage('Workspace analysis completed');
    } catch (error) {
      vscode.window.showErrorMessage(`Analysis failed: ${error}`);
    }
  });

  // Command to show node details (internal use)
  const showNodeDetailsCommand = vscode.commands.registerCommand('codexAura.showNodeDetails', async (nodeId: string) => {
    // This command is called from the graph view
    // The node view provider will handle showing the details
    await vscode.commands.executeCommand('workbench.view.extension.codexAura-node');
  });

  context.subscriptions.push(showGraphCommand, analyzeCommand, showNodeDetailsCommand);
}