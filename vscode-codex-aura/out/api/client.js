"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CodexAuraClient = void 0;
class CodexAuraClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }
    async getGraphs() {
        const response = await fetch(`${this.baseUrl}/api/v1/graphs`);
        if (!response.ok) {
            throw new Error(`Failed to fetch graphs: ${response.statusText}`);
        }
        return response.json();
    }
    async getGraph(graphId) {
        const response = await fetch(`${this.baseUrl}/api/v1/graph/${graphId}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch graph ${graphId}: ${response.statusText}`);
        }
        return response.json();
    }
    async getNode(graphId, nodeId) {
        const response = await fetch(`${this.baseUrl}/api/v1/graph/${graphId}/node/${encodeURIComponent(nodeId)}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch node ${nodeId}: ${response.statusText}`);
        }
        return response.json();
    }
    async getDependencies(graphId, nodeId, depth = 1) {
        const response = await fetch(`${this.baseUrl}/api/v1/graph/${graphId}/node/${encodeURIComponent(nodeId)}/dependencies?depth=${depth}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch dependencies for node ${nodeId}: ${response.statusText}`);
        }
        return response.json();
    }
}
exports.CodexAuraClient = CodexAuraClient;
//# sourceMappingURL=client.js.map