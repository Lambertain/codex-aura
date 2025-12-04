"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.NodeViewProvider = void 0;
const vscode = __importStar(require("vscode"));
const client_1 = require("../api/client");
class NodeViewProvider {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
        const config = vscode.workspace.getConfiguration('codexAura');
        const serverUrl = config.get('serverUrl', 'http://localhost:8000');
        this.client = new client_1.CodexAuraClient(serverUrl);
    }
    resolveWebviewView(webviewView, context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };
        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'showNodeDetails':
                    await this.showNodeDetails(message.nodeId);
                    break;
            }
        }, undefined, []);
    }
    async showNodeDetails(nodeId) {
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
        }
        catch (error) {
            vscode.window.showErrorMessage(`Failed to load node details: ${error}`);
        }
    }
    setCurrentGraph(graphId) {
        this.currentGraphId = graphId;
    }
    _getHtmlForWebview(webview) {
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
exports.NodeViewProvider = NodeViewProvider;
NodeViewProvider.viewType = 'codexAura.nodeView';
function getNonce() {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
//# sourceMappingURL=nodeView.js.map