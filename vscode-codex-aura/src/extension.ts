import * as vscode from 'vscode';
import { GraphViewProvider } from './views/graphView';
import { registerCommands } from './commands/commands';

export function activate(context: vscode.ExtensionContext) {
  console.log('Codex Aura extension is now active!');

  // Register commands
  registerCommands(context);

  // Register WebView provider for graph visualization
  const graphViewProvider = new GraphViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(GraphViewProvider.viewType, graphViewProvider)
  );

  // Register panel for node details
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('codexAura.nodeView', {
      resolveWebviewView(webviewView: vscode.WebviewView) {
        webviewView.webview.html = getNodeViewHtml(webviewView.webview);
      }
    })
  );
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