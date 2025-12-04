import * as vscode from 'vscode';
import { CodexAuraClient } from './api/client';

interface ImpactData {
  changed_files: string[];
  affected_files: Array<{
    path: string;
    impact_type: string;
    edges?: string[];
    distance?: number;
  }>;
  affected_tests: string[];
}

export class ImpactDecoratorProvider implements vscode.FileDecorationProvider {
  private client: CodexAuraClient;
  private impactCache = new Map<string, ImpactData>();
  private disposables: vscode.Disposable[] = [];

  constructor(client: CodexAuraClient) {
    this.client = client;
  }

  provideFileDecoration(uri: vscode.Uri): vscode.FileDecoration | undefined {
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
      } else if (impactCount > 5) {
        return {
          badge: '🟡',
          tooltip: `Medium impact: affects ${impactCount} files`,
          color: new vscode.ThemeColor('charts.yellow')
        };
      } else if (impactCount > 0) {
        return {
          badge: '🟢',
          tooltip: `Low impact: affects ${impactCount} files`,
          color: new vscode.ThemeColor('charts.green')
        };
      }
    }

    return undefined;
  }

  async updateImpactCache(filePath: string): Promise<void> {
    try {
      const graphs = await this.client.getGraphs();
      if (graphs.length === 0) return;

      const graphId = graphs[0].id;
      const response = await fetch(`${this.client.getBaseUrl()}/api/v1/graph/${graphId}/impact?files=${encodeURIComponent(filePath)}`);
      if (response.ok) {
        const impactData = await response.json() as ImpactData;
        this.impactCache.set(filePath, impactData);
        // Trigger refresh of decorations
        this.disposables.forEach(d => d.dispose());
        this.registerProvider();
      }
    } catch (error) {
      console.error('Failed to update impact cache:', error);
    }
  }

  registerProvider(): void {
    const provider = vscode.window.registerFileDecorationProvider(this);
    this.disposables.push(provider);
  }

  dispose(): void {
    this.disposables.forEach(d => d.dispose());
  }
}

export class HoverProvider implements vscode.HoverProvider {
  private client: CodexAuraClient;

  constructor(client: CodexAuraClient) {
    this.client = client;
  }

  async provideHover(document: vscode.TextDocument, position: vscode.Position): Promise<vscode.Hover | undefined> {
    // Only provide hover for file explorer items
    if (document.uri.scheme !== 'file') return;

    const filePath = vscode.workspace.asRelativePath(document.uri);

    try {
      const graphs = await this.client.getGraphs();
      if (graphs.length === 0) return;

      const graphId = graphs[0].id;
      const response = await fetch(`${this.client.getBaseUrl()}/api/v1/graph/${graphId}/impact?files=${encodeURIComponent(filePath)}`);
      if (!response.ok) return;

      const impactData = await response.json() as ImpactData;

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
    } catch (error) {
      console.error('Failed to provide hover:', error);
      return undefined;
    }
  }
}