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
const extension_1 = require("../extension");
function registerCommands(context) {
    const config = vscode.workspace.getConfiguration('codexAura');
    const serverUrl = config.get('serverUrl', 'http://localhost:8000');
    const client = new client_1.CodexAuraClient(serverUrl);
    // Command to show graph
    const showGraphCommand = vscode.commands.registerCommand('codexAura.showGraph', async (graphId) => {
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
                }
                else {
                    return;
                }
            }
            // Open the graph view
            await vscode.commands.executeCommand('workbench.view.extension.codexAura-graph');
            // Load the graph
            const graphViewProvider = (0, extension_1.getGraphViewProvider)();
            if (graphViewProvider) {
                await graphViewProvider.loadGraphById(selectedGraphId);
            }
            // For now, we'll need to modify the graph view to accept the graphId
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
        (0, extension_1.setAnalyzingStatus)(true);
        try {
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Analyzing codebase...",
                cancellable: false
            }, async (progress) => {
                const result = await client.analyze(workspaceFolder.uri.fsPath);
                vscode.commands.executeCommand('codexAura.showGraph', result.graph_id);
            });
        }
        catch (error) {
            vscode.window.showErrorMessage(`Analysis failed: ${error}`);
        }
        finally {
            (0, extension_1.setAnalyzingStatus)(false);
        }
    });
    // Command to show node details (internal use)
    const showNodeDetailsCommand = vscode.commands.registerCommand('codexAura.showNodeDetails', async (nodeId, graphId) => {
        // This command is called from the graph view
        // The node view provider will handle showing the details
        await vscode.commands.executeCommand('workbench.view.extension.codexAura-node');
        // TODO: Pass graphId to node view provider
    });
    // Command to show dependencies for a file
    const showDependenciesCommand = vscode.commands.registerCommand('codexAura.showDependencies', async (uri) => {
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
//# sourceMappingURL=commands.js.map