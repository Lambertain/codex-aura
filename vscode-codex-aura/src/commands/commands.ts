import * as vscode from 'vscode';
import { CodexAuraClient } from '../api/client';
import { getGraphViewProvider, setAnalyzingStatus } from '../extension';

interface GraphNode {
  id: string;
  path: string;
  type: string;
  name: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: any[];
}

interface ContextNode {
  id: string;
  type: string;
  path: string;
  code?: string;
  relevance: number;
}

interface ContextResponse {
  context_nodes: ContextNode[];
  total_nodes: number;
  truncated: boolean;
}

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

  // Command to preview impact of a file
  const previewImpactCommand = vscode.commands.registerCommand('codexAura.previewImpact', async (uri?: vscode.Uri) => {
    const fileUri = uri || vscode.window.activeTextEditor?.document.uri;
    if (!fileUri) {
      vscode.window.showErrorMessage('No file selected');
      return;
    }

    try {
      // Get current graph
      const graphs = await client.getGraphs();
      if (graphs.length === 0) {
        vscode.window.showErrorMessage('No graphs available. Please analyze the workspace first.');
        return;
      }

      // Use the first graph for now (could be made configurable)
      const graphId = graphs[0].id;
      const filePath = vscode.workspace.asRelativePath(fileUri);

      // Call impact API
       const response = await fetch(`${client.getBaseUrl()}/api/v1/graph/${graphId}/impact?files=${encodeURIComponent(filePath)}`);
       if (!response.ok) {
         throw new Error(`Failed to get impact: ${response.statusText}`);
       }

       const impactData = await response.json() as { affected_files: any[], affected_tests: string[] };

      // Show impact preview
      const message = `Impact of ${filePath}:\n` +
        `Directly affected: ${impactData.affected_files.filter((f: any) => f.impact_type === 'direct').length} files\n` +
        `Transitively affected: ${impactData.affected_files.filter((f: any) => f.impact_type === 'transitive').length} files\n` +
        `Affected tests: ${impactData.affected_tests.length}`;

      const choice = await vscode.window.showInformationMessage(message, 'Show Details', 'Highlight in Graph');

      if (choice === 'Show Details') {
        // Show detailed impact information
        const details = impactData.affected_files.map((f: any) =>
          `${f.path} (${f.impact_type}${f.distance ? `, distance: ${f.distance}` : ''})`
        ).join('\n');
        vscode.window.showInformationMessage(`Affected files:\n${details}`);
      } else if (choice === 'Highlight in Graph') {
        // Open graph view and highlight affected files
        await vscode.commands.executeCommand('workbench.view.extension.codexAura-graph');
        const graphViewProvider = getGraphViewProvider();
        if (graphViewProvider) {
          await graphViewProvider.loadGraphById(graphId);
          // TODO: Implement highlighting of affected files
          vscode.window.showInformationMessage('Graph opened. Highlighting feature to be implemented.');
        }
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to preview impact: ${error}`);
    }
  });

  // Command to get context for task
  const getContextCommand = vscode.commands.registerCommand('codexAura.getContext', async () => {
    // Get task description from user
    const taskDescription = await vscode.window.showInputBox({
      prompt: 'Describe your task',
      placeHolder: 'e.g., Implement user authentication, fix login bug, add new feature...'
    });

    if (!taskDescription) {
      return;
    }

    try {
      // Get current graph
      const graphs = await client.getGraphs();
      if (graphs.length === 0) {
        vscode.window.showErrorMessage('No graphs available. Please analyze the workspace first.');
        return;
      }

      const graphId = graphs[0].id;

      // Show progress
      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: 'Getting context for task...',
        cancellable: false
      }, async (progress) => {
        // For now, get context based on current file or selection
        const editor = vscode.window.activeTextEditor;
        let entryPoints: string[] = [];

        if (editor) {
          const document = editor.document;
          const filePath = vscode.workspace.asRelativePath(document.uri);

          // Find nodes in current file
          const response = await fetch(`${client.getBaseUrl()}/api/v1/graph/${graphId}`);
          if (response.ok) {
            const graph = await response.json() as GraphData;
            const fileNodes = graph.nodes.filter(n => n.path === filePath);
            entryPoints = fileNodes.map(n => n.id);
          }
        }

        if (entryPoints.length === 0) {
          vscode.window.showErrorMessage('No entry points found. Please open a file or select code.');
          return;
        }

        // Get context
        const contextResponse = await fetch(`${client.getBaseUrl()}/api/v1/context`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            graph_id: graphId,
            entry_points: entryPoints.slice(0, 5), // Limit to 5 entry points
            depth: 2,
            include_code: true,
            max_nodes: 50
          }),
        });

        if (!contextResponse.ok) {
          throw new Error(`Failed to get context: ${contextResponse.statusText}`);
        }

        const contextData = await contextResponse.json() as ContextResponse;

        // Show preview
        const previewContent = contextData.context_nodes.map(node =>
          `**${node.type}**: ${node.path}\n${node.code ? '```\n' + node.code.slice(0, 200) + '...\n```' : ''}`
        ).join('\n\n');

        const choice = await vscode.window.showInformationMessage(
          `Context gathered: ${contextData.context_nodes.length} nodes`,
          'Copy to Clipboard',
          'Insert at Cursor',
          'Open in New File'
        );

        if (choice === 'Copy to Clipboard') {
          await vscode.env.clipboard.writeText(previewContent);
          vscode.window.showInformationMessage('Context copied to clipboard');
        } else if (choice === 'Insert at Cursor') {
          const editor = vscode.window.activeTextEditor;
          if (editor) {
            const position = editor.selection.active;
            await editor.edit(editBuilder => {
              editBuilder.insert(position, previewContent);
            });
          }
        } else if (choice === 'Open in New File') {
          const document = await vscode.workspace.openTextDocument({
            content: previewContent,
            language: 'markdown'
          });
          await vscode.window.showTextDocument(document);
        }
      });
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to get context: ${error}`);
    }
  });

  context.subscriptions.push(showGraphCommand, analyzeCommand, showNodeDetailsCommand, showDependenciesCommand, showFunctionDependenciesCommand, openSettingsCommand, previewImpactCommand, getContextCommand);
}