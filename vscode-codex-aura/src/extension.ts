import * as vscode from 'vscode';
import { GraphViewProvider } from './views/graphView';
import { NodeViewProvider } from './views/nodeView';
import { registerCommands } from './commands/commands';
import { CodexAuraClient } from './api/client';
import { ImpactDecoratorProvider, HoverProvider } from './treeDecorators';
import { InlineDecorationsProvider } from './decorations';

let graphViewProvider: GraphViewProvider;
let statusBarItem: vscode.StatusBarItem;
let client: CodexAuraClient;
let statusCheckInterval: NodeJS.Timeout;
let updateTimeout: NodeJS.Timeout;
let isAnalyzing = false;

async function updateStatus() {
  if (!statusBarItem) return;

  try {
    if (isAnalyzing) {
      statusBarItem.text = '$(sync~spin) Analyzing...';
      statusBarItem.tooltip = 'Codex Aura is analyzing the codebase';
      statusBarItem.backgroundColor = undefined;
    } else {
      // Check server connection
      await client.getGraphs();
      statusBarItem.text = '$(database) Codex Aura: Ready';
      statusBarItem.tooltip = 'Codex Aura server is connected and ready';
      statusBarItem.backgroundColor = undefined;
    }
  } catch (error) {
    statusBarItem.text = '$(warning) Codex Aura: Not Connected';
    statusBarItem.tooltip = `Codex Aura server is not available: ${error}`;
    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
  }

  statusBarItem.show();
}

export function setAnalyzingStatus(analyzing: boolean) {
  isAnalyzing = analyzing;
  updateStatus();
}

export function activate(context: vscode.ExtensionContext) {
  console.log('Codex Aura extension is now active!');

  // Initialize client
  const config = vscode.workspace.getConfiguration('codexAura');
  const serverUrl = config.get<string>('serverUrl', 'http://localhost:8000');
  client = new CodexAuraClient(serverUrl);

  // Register commands
  registerCommands(context);

  // Register WebView provider for graph visualization
  graphViewProvider = new GraphViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(GraphViewProvider.viewType, graphViewProvider)
  );

  // Register panel for node details
  const nodeViewProvider = new NodeViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(NodeViewProvider.viewType, nodeViewProvider)
  );

  // Register tree decorators and hover providers
  const impactDecorator = new ImpactDecoratorProvider(client);
  const hoverProvider = new HoverProvider(client);
  const inlineDecorations = new InlineDecorationsProvider(client);

  context.subscriptions.push(
    vscode.window.registerFileDecorationProvider(impactDecorator),
    vscode.languages.registerHoverProvider({ scheme: 'file' }, hoverProvider),
    inlineDecorations
  );

  // Update decorations when active editor changes
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(editor => {
      if (editor) {
        inlineDecorations.updateDecorations(editor);
      }
    })
  );

  // Update decorations when document changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument(event => {
      const editor = vscode.window.activeTextEditor;
      if (editor && event.document === editor.document) {
        // Debounce updates
        clearTimeout(updateTimeout);
        updateTimeout = setTimeout(() => {
          inlineDecorations.updateDecorations(editor);
        }, 500);
      }
    })
  );

  // Create status bar item
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.command = 'codexAura.openSettings';
  context.subscriptions.push(statusBarItem);

  // Start status checking
  updateStatus();
  statusCheckInterval = setInterval(updateStatus, 30000); // Check every 30 seconds
  context.subscriptions.push({ dispose: () => clearInterval(statusCheckInterval) });

  // Listen for configuration changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration('codexAura.serverUrl')) {
        const newConfig = vscode.workspace.getConfiguration('codexAura');
        const newServerUrl = newConfig.get<string>('serverUrl', 'http://localhost:8000');
        client = new CodexAuraClient(newServerUrl);
        updateStatus();
      }
    })
  );
}

export function getGraphViewProvider(): GraphViewProvider {
  return graphViewProvider;
}

function getNodeViewHtml(webview: vscode.Webview): string {
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>Node Details</title>
    </head>
    <body>
      <h2>Node Details</h2>
      <div id="node-details">Select a node to view details</div>
    </body>
    </html>
  `;
}

export function deactivate() {}