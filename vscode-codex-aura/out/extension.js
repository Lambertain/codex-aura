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
exports.setAnalyzingStatus = setAnalyzingStatus;
exports.activate = activate;
exports.getGraphViewProvider = getGraphViewProvider;
exports.getTelemetryManager = getTelemetryManager;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const graphView_1 = require("./views/graphView");
const nodeView_1 = require("./views/nodeView");
const commands_1 = require("./commands/commands");
const client_1 = require("./api/client");
const treeDecorators_1 = require("./treeDecorators");
const decorations_1 = require("./decorations");
const telemetry_1 = require("./telemetry");
let graphViewProvider;
let statusBarItem;
let client;
let telemetryManager;
let statusCheckInterval;
let updateTimeout;
let isAnalyzing = false;
async function updateStatus() {
    if (!statusBarItem)
        return;
    try {
        if (isAnalyzing) {
            statusBarItem.text = '$(sync~spin) Analyzing...';
            statusBarItem.tooltip = 'Codex Aura is analyzing the codebase';
            statusBarItem.backgroundColor = undefined;
        }
        else {
            // Check server connection
            await client.getGraphs();
            statusBarItem.text = '$(database) Codex Aura: Ready';
            statusBarItem.tooltip = 'Codex Aura server is connected and ready';
            statusBarItem.backgroundColor = undefined;
        }
    }
    catch (error) {
        statusBarItem.text = '$(warning) Codex Aura: Not Connected';
        statusBarItem.tooltip = `Codex Aura server is not available: ${error}`;
        statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
    }
    statusBarItem.show();
}
function setAnalyzingStatus(analyzing) {
    isAnalyzing = analyzing;
    updateStatus();
}
function activate(context) {
    console.log('Codex Aura extension is now active!');
    // Initialize telemetry
    telemetryManager = new telemetry_1.TelemetryManager(context);
    // Show opt-in dialog for telemetry
    setTimeout(async () => {
        try {
            await telemetryManager.showOptInDialog();
        }
        catch (error) {
            console.log('Telemetry opt-in dialog failed:', error);
        }
    }, 5000); // Show after 5 seconds to not interrupt user immediately
    // Initialize client
    const config = vscode.workspace.getConfiguration('codexAura');
    const serverUrl = config.get('serverUrl', 'http://localhost:8000');
    const autoAnalyze = config.get('autoAnalyze', true);
    client = new client_1.CodexAuraClient(serverUrl);
    // Auto-analyze workspace if enabled
    if (autoAnalyze && vscode.workspace.workspaceFolders) {
        // Delay auto-analysis to allow extension to fully initialize
        setTimeout(async () => {
            try {
                const graphs = await client.getGraphs();
                if (graphs.length === 0) {
                    // No graphs exist, analyze the workspace
                    await vscode.commands.executeCommand('codexAura.analyze');
                }
            }
            catch (error) {
                console.log('Auto-analysis skipped due to server connection issue');
            }
        }, 2000);
    }
    // Register commands
    (0, commands_1.registerCommands)(context);
    // Register WebView provider for graph visualization
    graphViewProvider = new graphView_1.GraphViewProvider(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(graphView_1.GraphViewProvider.viewType, graphViewProvider));
    // Register panel for node details
    const nodeViewProvider = new nodeView_1.NodeViewProvider(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(nodeView_1.NodeViewProvider.viewType, nodeViewProvider));
    // Register tree decorators and hover providers
    const impactDecorator = new treeDecorators_1.ImpactDecoratorProvider(client);
    const hoverProvider = new treeDecorators_1.HoverProvider(client);
    const inlineDecorations = new decorations_1.InlineDecorationsProvider(client);
    context.subscriptions.push(vscode.window.registerFileDecorationProvider(impactDecorator), vscode.languages.registerHoverProvider({ scheme: 'file' }, hoverProvider), inlineDecorations);
    // Update decorations when active editor changes
    context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(editor => {
        if (editor) {
            inlineDecorations.updateDecorations(editor);
        }
    }));
    // Update decorations when document changes
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument(event => {
        const editor = vscode.window.activeTextEditor;
        if (editor && event.document === editor.document) {
            // Debounce updates
            clearTimeout(updateTimeout);
            updateTimeout = setTimeout(() => {
                inlineDecorations.updateDecorations(editor);
            }, 500);
        }
    }));
    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.command = 'codexAura.openSettings';
    context.subscriptions.push(statusBarItem);
    // Start status checking
    updateStatus();
    statusCheckInterval = setInterval(updateStatus, 30000); // Check every 30 seconds
    context.subscriptions.push({ dispose: () => clearInterval(statusCheckInterval) });
    // Listen for configuration changes
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('codexAura.serverUrl')) {
            const newConfig = vscode.workspace.getConfiguration('codexAura');
            const newServerUrl = newConfig.get('serverUrl', 'http://localhost:8000');
            // Validate server URL
            try {
                new URL(newServerUrl);
                client = new client_1.CodexAuraClient(newServerUrl);
                updateStatus();
            }
            catch (error) {
                vscode.window.showErrorMessage(`Invalid server URL: ${newServerUrl}`);
            }
        }
        if (e.affectsConfiguration('codexAura.defaultContextDepth')) {
            const newConfig = vscode.workspace.getConfiguration('codexAura');
            const depth = newConfig.get('defaultContextDepth', 2);
            if (depth < 1 || depth > 10) {
                vscode.window.showWarningMessage('Context depth must be between 1 and 10');
            }
        }
        if (e.affectsConfiguration('codexAura.defaultMaxTokens')) {
            const newConfig = vscode.workspace.getConfiguration('codexAura');
            const tokens = newConfig.get('defaultMaxTokens', 8000);
            if (tokens < 1000 || tokens > 50000) {
                vscode.window.showWarningMessage('Max tokens must be between 1000 and 50000');
            }
        }
    }));
}
function getGraphViewProvider() {
    return graphViewProvider;
}
function getTelemetryManager() {
    return telemetryManager;
}
function getNodeViewHtml(webview) {
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
function deactivate() { }
//# sourceMappingURL=extension.js.map