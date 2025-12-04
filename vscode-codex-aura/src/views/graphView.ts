import * as vscode from 'vscode';
import { CodexAuraClient, Graph, Node, Edge } from '../api/client';

export class GraphViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'codexAura.graphView';

  private _view?: vscode.WebviewView;
  private client: CodexAuraClient;

  constructor(private readonly _extensionUri: vscode.Uri) {
    const config = vscode.workspace.getConfiguration('codexAura');
    const serverUrl = config.get<string>('serverUrl', 'http://localhost:8000');
    this.client = new CodexAuraClient(serverUrl);
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(
      async (message) => {
        switch (message.command) {
          case 'loadGraph':
            await this.loadGraph(message.graphId);
            break;
          case 'nodeClicked':
            this.showNodeDetails(message.nodeId);
            break;
        }
      },
      undefined,
      []
    );
  }

  public async loadGraphById(graphId: string) {
    this.currentGraphId = graphId;
    await this.loadGraph(graphId);
  }

  private async loadGraph(graphId: string) {
    try {
      const graph = await this.client.getGraph(graphId);
      this._view?.webview.postMessage({
        command: 'updateGraph',
        graph: graph
      });
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to load graph: ${error}`);
    }
  }

  private showNodeDetails(nodeId: string) {
    // This will be handled by the node view provider
    vscode.commands.executeCommand('codexAura.showNodeDetails', nodeId, this.currentGraphId);
  }

  private currentGraphId?: string;

  public setCurrentGraphId(graphId: string) {
    this.currentGraphId = graphId;
  }

  private _getHtmlForWebview(webview: vscode.Webview) {
    const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'graph.js'));
    const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._extensionUri, 'media', 'graph.css'));

    const nonce = getNonce();

    return `<!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="${styleUri}" rel="stylesheet">
        <script src="https://d3js.org/d3.v7.min.js" nonce="${nonce}"></script>
        <title>Code Graph</title>
      </head>
      <body>
        <div id="graph-container">
          <div id="graph"></div>
        </div>
        <script nonce="${nonce}">
          const vscode = acquireVsCodeApi();

          // D3 force-directed graph implementation
          let svg, simulation, nodes, links;

          function initializeGraph() {
            const width = document.getElementById('graph').clientWidth;
            const height = document.getElementById('graph').clientHeight;

            svg = d3.select('#graph')
              .append('svg')
              .attr('width', width)
              .attr('height', height);

            simulation = d3.forceSimulation()
              .force('link', d3.forceLink().id(d => d.id).distance(100))
              .force('charge', d3.forceManyBody().strength(-300))
              .force('center', d3.forceCenter(width / 2, height / 2));

            links = svg.append('g').attr('class', 'links');
            nodes = svg.append('g').attr('class', 'nodes');
          }

          window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
              case 'updateGraph':
                updateGraph(message.graph);
                break;
            }
          });

          function updateGraph(graph) {
            // Update links
            links.selectAll('line')
              .data(graph.edges)
              .join('line')
              .attr('stroke', d => getEdgeColor(d.type))
              .attr('stroke-width', 2);

            // Update nodes
            const nodeElements = nodes.selectAll('circle')
              .data(graph.nodes)
              .join('circle')
              .attr('r', 10)
              .attr('fill', d => getNodeColor(d.type))
              .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended))
              .on('click', (event, d) => {
                vscode.postMessage({
                  command: 'nodeClicked',
                  nodeId: d.id
                });
              });

            // Add labels
            nodes.selectAll('text')
              .data(graph.nodes)
              .join('text')
              .attr('dx', 12)
              .attr('dy', '.35em')
              .text(d => d.label);

            simulation
              .nodes(graph.nodes)
              .on('tick', ticked);

            simulation.force('link')
              .links(graph.edges);

            simulation.alpha(1).restart();
          }

          function ticked() {
            links.selectAll('line')
              .attr('x1', d => d.source.x)
              .attr('y1', d => d.source.y)
              .attr('x2', d => d.target.x)
              .attr('y2', d => d.target.y);

            nodes.selectAll('circle')
              .attr('cx', d => d.x)
              .attr('cy', d => d.y);

            nodes.selectAll('text')
              .attr('x', d => d.x)
              .attr('y', d => d.y);
          }

          function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          }

          function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
          }

          function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }

          function getNodeColor(type) {
            const colors = {
              'function': '#4CAF50',
              'class': '#2196F3',
              'variable': '#FF9800',
              'module': '#9C27B0'
            };
            return colors[type] || '#757575';
          }

          function getEdgeColor(type) {
            const colors = {
              'calls': '#4CAF50',
              'inherits': '#2196F3',
              'imports': '#FF9800',
              'references': '#9C27B0'
            };
            return colors[type] || '#757575';
          }

          initializeGraph();
        </script>
      </body>
      </html>`;
  }
}

function getNonce() {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}