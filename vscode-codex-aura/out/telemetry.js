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
exports.TelemetryManager = void 0;
const vscode = __importStar(require("vscode"));
class TelemetryManager {
    constructor(context) {
        this.isEnabled = false;
        this.events = [];
        this.maxEvents = 100;
        this.context = context;
        this.loadSettings();
    }
    loadSettings() {
        const config = vscode.workspace.getConfiguration('codexAura');
        this.isEnabled = config.get('telemetryEnabled', false);
    }
    async showOptInDialog() {
        const hasShownOptIn = this.context.globalState.get('codexAura.telemetryOptInShown', false);
        if (hasShownOptIn) {
            return this.isEnabled;
        }
        const choice = await vscode.window.showInformationMessage('Codex Aura collects anonymous usage data to improve the extension. This includes command usage, graph sizes, and error reports. No personal information or code content is collected.', 'Enable Telemetry', 'Disable Telemetry', 'Learn More');
        if (choice === 'Learn More') {
            vscode.env.openExternal(vscode.Uri.parse('https://github.com/Lambertain/codex-aura/blob/main/PRIVACY.md'));
            // Re-show dialog after opening privacy policy
            return this.showOptInDialog();
        }
        const enabled = choice === 'Enable Telemetry';
        await this.context.globalState.update('codexAura.telemetryOptInShown', true);
        if (enabled) {
            await this.enableTelemetry();
        }
        return enabled;
    }
    async enableTelemetry() {
        this.isEnabled = true;
        const config = vscode.workspace.getConfiguration('codexAura');
        await config.update('telemetryEnabled', true, vscode.ConfigurationTarget.Global);
    }
    async disableTelemetry() {
        this.isEnabled = false;
        const config = vscode.workspace.getConfiguration('codexAura');
        await config.update('telemetryEnabled', false, vscode.ConfigurationTarget.Global);
    }
    trackEvent(event, properties) {
        if (!this.isEnabled)
            return;
        const telemetryEvent = {
            event,
            properties,
            timestamp: Date.now()
        };
        this.events.push(telemetryEvent);
        // Keep only the last maxEvents events
        if (this.events.length > this.maxEvents) {
            this.events = this.events.slice(-this.maxEvents);
        }
        // In a real implementation, you would send this to a telemetry service
        console.log('Telemetry event:', telemetryEvent);
    }
    trackCommand(command) {
        this.trackEvent('command_executed', { command });
    }
    trackGraphSize(graphId, nodeCount) {
        this.trackEvent('graph_analyzed', { graphId, nodeCount });
    }
    trackError(error, context) {
        this.trackEvent('error_occurred', {
            message: error.message,
            stack: error.stack?.substring(0, 500), // Limit stack trace length
            context
        });
    }
    getEvents() {
        return [...this.events];
    }
    clearEvents() {
        this.events = [];
    }
    isTelemetryEnabled() {
        return this.isEnabled;
    }
}
exports.TelemetryManager = TelemetryManager;
//# sourceMappingURL=telemetry.js.map