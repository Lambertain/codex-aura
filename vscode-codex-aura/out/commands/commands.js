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
exports.registerCommands = registerCommands;
const vscode = __importStar(require("vscode"));
const client_1 = require("../api/client");
function registerCommands(context) {
    const config = vscode.workspace.getConfiguration('codexAura');
    const serverUrl = config.get('serverUrl', 'http://localhost:8000');
    const client = new client_1.CodexAuraClient(serverUrl);
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
        }
        catch (error) {
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
        }
        catch (error) {
            vscode.window.showErrorMessage(`Analysis failed: ${error}`);
        }
    });
    // Command to show node details (internal use)
    const showNodeDetailsCommand = vscode.commands.registerCommand('codexAura.showNodeDetails', async (nodeId) => {
        // This command is called from the graph view
        // The node view provider will handle showing the details
        await vscode.commands.executeCommand('workbench.view.extension.codexAura-node');
    });
    context.subscriptions.push(showGraphCommand, analyzeCommand, showNodeDetailsCommand);
}
//# sourceMappingURL=commands.js.map