export interface Graph {
  id: string;
  name: string;
  nodes: Node[];
  edges: Edge[];
}

export interface Node {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

export interface Edge {
  from: string;
  to: string;
  type: string;
  properties: Record<string, any>;
}

export interface NodeDetails {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
  dependencies: string[];
  dependents: string[];
  path?: string;
  docstring?: string;
  signature?: string;
  code?: string;
}

export interface SubGraph {
  nodes: Node[];
  edges: Edge[];
}

export class CodexAuraClient {
  constructor(private baseUrl: string) {}

  getBaseUrl(): string {
    return this.baseUrl;
  }

  async getGraphs(): Promise<Graph[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/graphs`);
    if (!response.ok) {
      throw new Error(`Failed to fetch graphs: ${response.statusText}`);
    }
    return response.json() as Promise<Graph[]>;
  }

  async getGraph(graphId: string): Promise<Graph> {
    const response = await fetch(`${this.baseUrl}/api/v1/graph/${graphId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch graph ${graphId}: ${response.statusText}`);
    }
    return response.json() as Promise<Graph>;
  }

  async getNode(graphId: string, nodeId: string): Promise<NodeDetails> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/graph/${graphId}/node/${encodeURIComponent(nodeId)}`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch node ${nodeId}: ${response.statusText}`);
    }
    return response.json() as Promise<NodeDetails>;
  }

  async getDependencies(graphId: string, nodeId: string, depth: number = 1): Promise<SubGraph> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/graph/${graphId}/node/${encodeURIComponent(nodeId)}/dependencies?depth=${depth}`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch dependencies for node ${nodeId}: ${response.statusText}`);
    }
    return response.json() as Promise<SubGraph>;
  }

  async analyze(path: string): Promise<{ graph_id: string }> {
    const response = await fetch(`${this.baseUrl}/api/v1/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ path }),
    });
    if (!response.ok) {
      throw new Error(`Failed to analyze workspace: ${response.statusText}`);
    }
    return response.json() as Promise<{ graph_id: string }>;
  }
}