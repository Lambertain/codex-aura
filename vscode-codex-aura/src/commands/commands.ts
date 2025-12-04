import * as vscode from 'vscode';
import { CodexAuraClient } from '../api/client';
import { getGraphViewProvider, setAnalyzingStatus } from '../extension';

export function registerCommands(context: vscode.ExtensionContext) {
  const config = vscode.workspace.getConfiguration('codexAura');
  const serverUrl = config.get<string>('serverUrl', 'http://localhost:8000');
  const client = new CodexAuraClient(serverUrl);

  // Command to show graph
  const showGraphCommand = vscode.commands.registerCommand('codexAura.showGraph', async (graphId?: string) => {
    try {
      let selectedGraphId = graphId;

      if (!selectedGraphId) {
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
          selectedGraphId = selectedGraph.graph.id;
        } else {
          return;
        }
      }

      // Open the graph view
      await vscode.commands.executeCommand('workbench.view.extension.codexAura-graph');
      // Load the graph
      const graphViewProvider = getGraphViewProvider();
      if (graphViewProvider) {
        await graphViewProvider.loadGraphById(selectedGraphId);
      }
      // For now, we'll need to modify the graph view to accept the graphId
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

    setAnalyzingStatus(true);
    try {
      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Analyzing codebase...",
        cancellable: false
      }, async (progress) => {
        const result = await client.analyze(workspaceFolder.uri.fsPath);
        vscode.commands.executeCommand('codexAura.showGraph', result.graph_id);
      });
    } catch (error) {
      vscode.window.showErrorMessage(`Analysis failed: ${error}`);
    } finally {
      setAnalyzingStatus(false);
    }
  });

  // Command to show node details (internal use)
  const showNodeDetailsCommand = vscode.commands.registerCommand('codexAura.showNodeDetails', async (nodeId: string, graphId?: string) => {
    // This command is called from the graph view
    // The node view provider will handle showing the details
    await vscode.commands.executeCommand('workbench.view.extension.codexAura-node');
    // TODO: Pass graphId to node view provider
  });

  // Command to show dependencies for a file
  const showDependenciesCommand = vscode.commands.registerCommand('codexAura.showDependencies', async (uri: vscode.Uri) => {
    // TODO: Implement showing dependencies for the file
    vscode.window.showInformationMessage(`Show dependencies for ${uri.fsPath}`);
  });

  // Command to show function dependencies
  const showFunctionDependenciesCommand = vscode.commands.registerCommand('codexAura.showFunctionDependencies', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showErrorMessage('No active editor');
      return;
    }

    // TODO: Get function at cursor and show its dependencies
    vscode.window.showInformationMessage('Show function dependencies');
  });

  // Command to open settings
  const openSettingsCommand = vscode.commands.registerCommand('codexAura.openSettings', () => {
    vscode.commands.executeCommand('workbench.action.openSettings', '@ext:codex-aura');
  });

  context.subscriptions.push(showGraphCommand, analyzeCommand, showNodeDetailsCommand, showDependenciesCommand, showFunctionDependenciesCommand, openSettingsCommand);
}