import * as vscode from 'vscode';

interface TelemetryEvent {
  event: string;
  properties?: Record<string, any>;
  timestamp: number;
}

export class TelemetryManager {
  private context: vscode.ExtensionContext;
  private isEnabled: boolean = false;
  private events: TelemetryEvent[] = [];
  private readonly maxEvents = 100;

  constructor(context: vscode.ExtensionContext) {
    this.context = context;
    this.loadSettings();
  }

  private loadSettings() {
    const config = vscode.workspace.getConfiguration('codexAura');
    this.isEnabled = config.get<boolean>('telemetryEnabled', false);
  }

  async showOptInDialog(): Promise<boolean> {
    const hasShownOptIn = this.context.globalState.get<boolean>('codexAura.telemetryOptInShown', false);

    if (hasShownOptIn) {
      return this.isEnabled;
    }

    const choice = await vscode.window.showInformationMessage(
      'Codex Aura collects anonymous usage data to improve the extension. This includes command usage, graph sizes, and error reports. No personal information or code content is collected.',
      'Enable Telemetry',
      'Disable Telemetry',
      'Learn More'
    );

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

  trackEvent(event: string, properties?: Record<string, any>) {
    if (!this.isEnabled) return;

    const telemetryEvent: TelemetryEvent = {
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

  trackCommand(command: string) {
    this.trackEvent('command_executed', { command });
  }

  trackGraphSize(graphId: string, nodeCount: number) {
    this.trackEvent('graph_analyzed', { graphId, nodeCount });
  }

  trackError(error: Error, context?: string) {
    this.trackEvent('error_occurred', {
      message: error.message,
      stack: error.stack?.substring(0, 500), // Limit stack trace length
      context
    });
  }

  getEvents(): TelemetryEvent[] {
    return [...this.events];
  }

  clearEvents() {
    this.events = [];
  }

  isTelemetryEnabled(): boolean {
    return this.isEnabled;
  }
}