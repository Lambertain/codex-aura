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
exports.HoverProvider = exports.ImpactDecoratorProvider = void 0;
const vscode = __importStar(require("vscode"));
class ImpactDecoratorProvider {
    constructor(client) {
        this.impactCache = new Map();
        this.disposables = [];
        this.client = client;
    }
    provideFileDecoration(uri) {
        const relativePath = vscode.workspace.asRelativePath(uri);
        const cached = this.impactCache.get(relativePath);
        if (cached) {
            const impactCount = cached.affected_files?.length || 0;
            if (impactCount > 10) {
                return {
                    badge: '🔴',
                    tooltip: `High impact: affects ${impactCount} files`,
                    color: new vscode.ThemeColor('charts.red')
                };
            }
            else if (impactCount > 5) {
                return {
                    badge: '🟡',
                    tooltip: `Medium impact: affects ${impactCount} files`,
                    color: new vscode.ThemeColor('charts.yellow')
                };
            }
            else if (impactCount > 0) {
                return {
                    badge: '🟢',
                    tooltip: `Low impact: affects ${impactCount} files`,
                    color: new vscode.ThemeColor('charts.green')
                };
            }
        }
        return undefined;
    }
    async updateImpactCache(filePath) {
        try {
            const graphs = await this.client.getGraphs();
            if (graphs.length === 0)
                return;
            const graphId = graphs[0].id;
            const response = await fetch(`${this.client.getBaseUrl()}/api/v1/graph/${graphId}/impact?files=${encodeURIComponent(filePath)}`);
            if (response.ok) {
                const impactData = await response.json();
                this.impactCache.set(filePath, impactData);
                // Trigger refresh of decorations
                this.disposables.forEach(d => d.dispose());
                this.registerProvider();
            }
        }
        catch (error) {
            console.error('Failed to update impact cache:', error);
        }
    }
    registerProvider() {
        const provider = vscode.window.registerFileDecorationProvider(this);
        this.disposables.push(provider);
    }
    dispose() {
        this.disposables.forEach(d => d.dispose());
    }
}
exports.ImpactDecoratorProvider = ImpactDecoratorProvider;
class HoverProvider {
    constructor(client) {
        this.client = client;
    }
    async provideHover(document, position) {
        // Only provide hover for file explorer items
        if (document.uri.scheme !== 'file')
            return;
        const filePath = vscode.workspace.asRelativePath(document.uri);
        try {
            const graphs = await this.client.getGraphs();
            if (graphs.length === 0)
                return;
            const graphId = graphs[0].id;
            const response = await fetch(`${this.client.getBaseUrl()}/api/v1/graph/${graphId}/impact?files=${encodeURIComponent(filePath)}`);
            if (!response.ok)
                return;
            const impactData = await response.json();
            const directAffected = impactData.affected_files.filter(f => f.impact_type === 'direct');
            const transitiveAffected = impactData.affected_files.filter(f => f.impact_type === 'transitive');
            const content = new vscode.MarkdownString();
            content.appendMarkdown(`## Impact Analysis for ${filePath}\n\n`);
            if (directAffected.length > 0) {
                content.appendMarkdown(`### Directly Affected Files (${directAffected.length})\n`);
                directAffected.slice(0, 5).forEach(file => {
                    content.appendMarkdown(`- ${file.path}\n`);
                });
                if (directAffected.length > 5) {
                    content.appendMarkdown(`- ... and ${directAffected.length - 5} more\n`);
                }
                content.appendMarkdown('\n');
            }
            if (transitiveAffected.length > 0) {
                content.appendMarkdown(`### Transitively Affected Files (${transitiveAffected.length})\n`);
                transitiveAffected.slice(0, 5).forEach(file => {
                    content.appendMarkdown(`- ${file.path} (distance: ${file.distance})\n`);
                });
                if (transitiveAffected.length > 5) {
                    content.appendMarkdown(`- ... and ${transitiveAffected.length - 5} more\n`);
                }
                content.appendMarkdown('\n');
            }
            if (impactData.affected_tests.length > 0) {
                content.appendMarkdown(`### Affected Tests (${impactData.affected_tests.length})\n`);
                impactData.affected_tests.slice(0, 3).forEach(test => {
                    content.appendMarkdown(`- ${test}\n`);
                });
                if (impactData.affected_tests.length > 3) {
                    content.appendMarkdown(`- ... and ${impactData.affected_tests.length - 3} more\n`);
                }
            }
            return new vscode.Hover(content);
        }
        catch (error) {
            console.error('Failed to provide hover:', error);
            return undefined;
        }
    }
}
exports.HoverProvider = HoverProvider;
//# sourceMappingURL=treeDecorators.js.map