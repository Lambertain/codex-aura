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
exports.InlineDecorationsProvider = void 0;
const vscode = __importStar(require("vscode"));
class InlineDecorationsProvider {
    constructor(client) {
        this.decorationTypes = new Map();
        this.disposables = [];
        this.client = client;
        this.createDecorationTypes();
    }
    createDecorationTypes() {
        // Gutter icon for dependency count
        this.decorationTypes.set('dependencyCount', vscode.window.createTextEditorDecorationType({
            gutterIconPath: this.getGutterIconPath('dependency'),
            gutterIconSize: 'contain'
        }));
        // Hot spot indicator
        this.decorationTypes.set('hotSpot', vscode.window.createTextEditorDecorationType({
            backgroundColor: new vscode.ThemeColor('editor.wordHighlightBackground'),
            border: '1px solid',
            borderColor: new vscode.ThemeColor('editor.wordHighlightBorder'),
            borderRadius: '2px'
        }));
        // Import count above file
        this.decorationTypes.set('importCount', vscode.window.createTextEditorDecorationType({
            after: {
                contentText: '',
                color: new vscode.ThemeColor('editorCodeLens.foreground'),
                fontStyle: 'italic'
            },
            rangeBehavior: vscode.DecorationRangeBehavior.ClosedClosed
        }));
    }
    getGutterIconPath(type) {
        // For now, return undefined - would need to include actual icon files
        return undefined;
    }
    async updateDecorations(editor) {
        if (!editor.document)
            return;
        const filePath = vscode.workspace.asRelativePath(editor.document.uri);
        try {
            const graphs = await this.client.getGraphs();
            if (graphs.length === 0)
                return;
            const graphId = graphs[0].id;
            // Get node details for this file
            const response = await fetch(`${this.client.getBaseUrl()}/api/v1/graph/${graphId}`);
            if (!response.ok)
                return;
            const graph = await response.json();
            const fileNodes = graph.nodes.filter(n => n.path === filePath);
            // Clear previous decorations
            this.decorationTypes.forEach(type => {
                editor.setDecorations(type, []);
            });
            // Apply dependency count decorations
            const dependencyDecorations = [];
            const hotSpotDecorations = [];
            for (const node of fileNodes) {
                if (node.type === 'function') {
                    // Get dependencies for this function
                    const depsResponse = await fetch(`${this.client.getBaseUrl()}/api/v1/graph/${graphId}/node/${encodeURIComponent(node.id)}/dependencies?depth=1`);
                    if (depsResponse.ok) {
                        const depsData = await depsResponse.json();
                        const dependencyCount = depsData.nodes?.length || 0;
                        // Find the function definition in the document
                        const functionRange = this.findFunctionRange(editor.document, node.name);
                        if (functionRange) {
                            // Add dependency count as hover
                            const decoration = {
                                range: functionRange,
                                hoverMessage: `${dependencyCount} dependencies`
                            };
                            dependencyDecorations.push(decoration);
                            // Mark as hot spot if high dependency count
                            if (dependencyCount > 5) {
                                hotSpotDecorations.push({
                                    range: functionRange,
                                    hoverMessage: `🔥 Hot spot: ${dependencyCount} dependencies`
                                });
                            }
                        }
                    }
                }
            }
            // Apply decorations
            if (dependencyDecorations.length > 0) {
                const depType = this.decorationTypes.get('dependencyCount');
                if (depType) {
                    editor.setDecorations(depType, dependencyDecorations);
                }
            }
            if (hotSpotDecorations.length > 0) {
                const hotType = this.decorationTypes.get('hotSpot');
                if (hotType) {
                    editor.setDecorations(hotType, hotSpotDecorations);
                }
            }
            // Add import count at the top
            this.addImportCountDecoration(editor, fileNodes.length);
        }
        catch (error) {
            console.error('Failed to update decorations:', error);
        }
    }
    findFunctionRange(document, functionName) {
        const text = document.getText();
        const lines = text.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            // Simple regex to find function definitions
            const functionRegex = new RegExp(`def\\s+${functionName}\\s*\\(`);
            if (functionRegex.test(line)) {
                const startPos = new vscode.Position(i, 0);
                const endPos = new vscode.Position(i, line.length);
                return new vscode.Range(startPos, endPos);
            }
        }
        return undefined;
    }
    addImportCountDecoration(editor, nodeCount) {
        const importType = this.decorationTypes.get('importCount');
        if (!importType)
            return;
        // Find the first non-empty, non-comment line
        const document = editor.document;
        for (let i = 0; i < Math.min(10, document.lineCount); i++) {
            const line = document.lineAt(i);
            const text = line.text.trim();
            if (text && !text.startsWith('#') && !text.startsWith('"""') && !text.startsWith("'''")) {
                const range = new vscode.Range(i, 0, i, 0);
                const decoration = {
                    range: range,
                    renderOptions: {
                        after: {
                            contentText: ` (${nodeCount} nodes)`,
                            color: new vscode.ThemeColor('editorCodeLens.foreground'),
                            fontStyle: 'italic'
                        }
                    }
                };
                editor.setDecorations(importType, [decoration]);
                break;
            }
        }
    }
    dispose() {
        this.decorationTypes.forEach(type => type.dispose());
        this.disposables.forEach(d => d.dispose());
    }
}
exports.InlineDecorationsProvider = InlineDecorationsProvider;
//# sourceMappingURL=decorations.js.map