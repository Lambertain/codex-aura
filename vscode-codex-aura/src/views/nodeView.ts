import * as vscode from 'vscode';
import { CodexAuraClient, NodeDetails } from '../api/client';

export class NodeViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'codexAura.nodeView';

  private _view?: vscode.WebviewView;
  private client: CodexAuraClient;
  private currentGraphId?: string;

  constructor(private readonly _extensionUri: vscode.Uri) {
    const config = vscode.workspace.getConfiguration('codexAura');
    const serverUrl = config.get<string>('serverUrl', 'http://localhost:8000');
    this.client = new CodexAuraClient(serverUrl);
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(
      async (message) => {
        switch (message.command) {
          case 'showNodeDetails':
            await this.showNodeDetails(message.nodeId);
            break;
        }
      },
      undefined,
      []
    );
  }

  public async showNodeDetails(nodeId: string) {
    if (!this.currentGraphId) {
      vscode.window.showErrorMessage('No graph selected');
      return;
    }

    try {
      const nodeDetails = await this.client.getNode(this.currentGraphId, nodeId);
      this._view?.webview.postMessage({
        command: 'updateNodeDetails',
        nodeDetails: nodeDetails
      });
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to load node details: ${error}`);
    }
  }

  public setCurrentGraph(graphId: string) {
    this.currentGraphId = graphId;
  }

  private _getHtmlForWebview(webview: vscode.Webview) {
    const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'graph.css'));
    const nonce = getNonce();

    return `<!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="${styleUri}" rel="stylesheet">
        <title>Node Details</title>
      </head>
      <body>
        <div id="node-details">
          <h3>Node Details</h3>
          <div id="node-content">
            <p>Select a node to view details</p>
          </div>
        </div>
        <script nonce="${nonce}">
          const vscode = acquireVsCodeApi();

          window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
              case 'updateNodeDetails':
                updateNodeDetails(message.nodeDetails);
                break;
            }
          });

          function updateNodeDetails(nodeDetails) {
            const content = document.getElementById('node-content');
            content.innerHTML = \`
              <h4>\${nodeDetails.label}</h4>
              <p><strong>Type:</strong> \${nodeDetails.type}</p>
              <p><strong>ID:</strong> \${nodeDetails.id}</p>
              <h5>Properties:</h5>
              <pre>\${JSON.stringify(nodeDetails.properties, null, 2)}</pre>
              <h5>Dependencies:</h5>
              <ul>
                \${nodeDetails.dependencies.map(dep => \`<li>\${dep}</li>\`).join('')}
              </ul>
              <h5>Dependents:</h5>
              <ul>
                \${nodeDetails.dependents.map(dep => \`<li>\${dep}</li>\`).join('')}
              </ul>
            \`;
          }
        </script>
      </body>
      </html>`;
  }
}

function getNonce() {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}