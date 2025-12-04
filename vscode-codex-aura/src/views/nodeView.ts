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
          case 'openFile':
            await this.openFile(message.filePath);
            break;
        }
      },
      undefined,
      []
    );
  }

  public async showNodeDetails(nodeId: string, graphId?: string) {
    const graphIdToUse = graphId || this.currentGraphId;
    if (!graphIdToUse) {
      vscode.window.showErrorMessage('No graph selected');
      return;
    }

    try {
      const nodeDetails = await this.client.getNode(graphIdToUse, nodeId);
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

  private async openFile(filePath: string) {
    try {
      const uri = vscode.Uri.file(filePath);
      await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(uri);
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to open file: ${error}`);
    }
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
        <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js" nonce="${nonce}"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js" nonce="${nonce}"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js" nonce="${nonce}"></script>
        <title>Node Details</title>
        <style>
          .clickable { cursor: pointer; color: #007acc; text-decoration: underline; }
          .clickable:hover { color: #005999; }
          pre { background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }
          code { font-family: 'Courier New', monospace; }
        </style>
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
            const name = nodeDetails.properties?.name || nodeDetails.label;
            const type = nodeDetails.type;
            const path = nodeDetails.properties?.path || nodeDetails.path;
            const docstring = nodeDetails.properties?.docstring || nodeDetails.docstring;
            const signature = nodeDetails.properties?.signature || nodeDetails.signature;
            const code = nodeDetails.properties?.code || nodeDetails.code;

            content.innerHTML = \`
              <h4>\${name}</h4>
              <p><strong>Type:</strong> \${type}</p>
              \${path ? \`<p><strong>Path:</strong> <span class="clickable" onclick="openFile('\${path}')">\${path}</span></p>\` : ''}
              \${docstring ? \`<h5>Docstring:</h5><p>\${docstring}</p>\` : ''}
              \${signature ? \`<h5>Signature:</h5><pre><code class="language-python">\${signature}</code></pre>\` : ''}
              <h5>Dependencies:</h5>
              <ul>
                \${nodeDetails.dependencies.map(dep => \`<li>\${dep}</li>\`).join('')}
              </ul>
              \${code ? \`<h5>Code:</h5><pre><code class="language-python">\${escapeHtml(code)}</code></pre>\` : ''}
            \`;

            // Re-run Prism highlighting
            Prism.highlightAll();
          }

          function openFile(filePath) {
            vscode.postMessage({
              command: 'openFile',
              filePath: filePath
            });
          }

          function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
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