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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const graphView_1 = require("./views/graphView");
const commands_1 = require("./commands/commands");
function activate(context) {
    console.log('Codex Aura extension is now active!');
    // Register commands
    (0, commands_1.registerCommands)(context);
    // Register WebView provider for graph visualization
    const graphViewProvider = new graphView_1.GraphViewProvider(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(graphView_1.GraphViewProvider.viewType, graphViewProvider));
    // Register panel for node details
    context.subscriptions.push(vscode.window.registerWebviewViewProvider('codexAura.nodeView', {
        resolveWebviewView(webviewView) {
            webviewView.webview.html = getNodeViewHtml(webviewView.webview);
        }
    }));
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