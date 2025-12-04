#!/usr/bin/env python3
"""Simple test server for graph visualization."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="Codex Aura Visualization Test")

# Mock data for testing - generate 500+ nodes
def generate_mock_graph():
    nodes = []
    edges = []

    # Generate files
    for i in range(50):
        file_id = f"module_{i}.py"
        nodes.append({
            "id": file_id,
            "type": "file",
            "name": f"module_{i}.py",
            "path": f"src/module_{i}.py",
            "docstring": f"Module {i} documentation"
        })

        # Generate classes in each file
        for j in range(3):
            class_id = f"Class{i}_{j}"
            nodes.append({
                "id": class_id,
                "type": "class",
                "name": f"Class{i}_{j}",
                "path": f"src/module_{i}.py",
                "lines": [10 + j*20, 25 + j*20],
                "docstring": f"Class {i}_{j} documentation"
            })

            # Generate methods in each class
            for k in range(5):
                func_id = f"method_{i}_{j}_{k}"
                nodes.append({
                    "id": func_id,
                    "type": "function",
                    "name": f"method_{i}_{j}_{k}",
                    "path": f"src/module_{i}.py",
                    "lines": [15 + j*20 + k*3, 17 + j*20 + k*3],
                    "docstring": f"Method {i}_{j}_{k} documentation"
                })

                # Add calls between methods
                if k > 0:
                    edges.append({
                        "source": func_id,
                        "target": f"method_{i}_{j}_{k-1}",
                        "type": "CALLS"
                    })

    # Generate standalone functions
    for i in range(100):
        func_id = f"func_{i}"
        nodes.append({
            "id": func_id,
            "type": "function",
            "name": f"func_{i}",
            "path": f"src/utils_{i//10}.py",
            "lines": [i*5, i*5 + 10],
            "docstring": f"Function {i} documentation"
        })

        # Add some imports
        if i % 10 == 0:
            edges.append({
                "source": f"module_{i//10}.py",
                "target": f"func_{i}",
                "type": "IMPORTS"
            })

        # Add some calls
        if i > 0 and i % 5 == 0:
            edges.append({
                "source": func_id,
                "target": f"func_{i-1}",
                "type": "CALLS"
            })

    return {"nodes": nodes, "edges": edges}

MOCK_GRAPH = generate_mock_graph()

@app.get("/api/v1/graphs")
async def get_graphs():
    """Get list of graphs."""
    return {
        "graphs": [
            {
                "id": "test-graph",
                "repo_name": "test-repo",
                "repo_path": "/test",
                "sha": "abc123",
                "created_at": "2025-01-01T00:00:00Z",
                "node_count": len(MOCK_GRAPH["nodes"]),
                "edge_count": len(MOCK_GRAPH["edges"])
            }
        ]
    }

@app.get("/api/v1/graph/{graph_id}")
async def get_graph(graph_id: str):
    """Get graph data."""
    return MOCK_GRAPH

@app.get("/api/v1/graph/{graph_id}/node/{node_id}")
async def get_node(graph_id: str, node_id: str, include_code: bool = False):
    """Get node details."""
    node = next((n for n in MOCK_GRAPH["nodes"] if n["id"] == node_id), None)
    if not node:
        return {"error": "Node not found"}

    # Mock code based on node type
    if include_code:
        node = dict(node)
        if node["type"] == "file":
            node["code"] = f'''"""
{node.get("docstring", "Module documentation")}
"""

# Module {node["name"]}
from typing import List, Dict, Any

class ExampleClass:
    """Example class in {node["name"]}"""

    def __init__(self):
        self.data = []

    def process(self, items: List[Any]) -> Dict[str, Any]:
        """Process items and return results."""
        return {{"processed": len(items)}}

def main():
    """Main function."""
    processor = ExampleClass()
    result = processor.process([1, 2, 3])
    print(f"Result: {{result}}")

if __name__ == "__main__":
    main()
'''
        elif node["type"] == "class":
            node["code"] = f'''class {node["name"]}:
    """
    {node.get("docstring", "Class documentation")}
    """

    def __init__(self):
        """Initialize {node["name"]}."""
        self._data = {{}}

    def method_one(self) -> str:
        """First method."""
        return "method_one result"

    def method_two(self, param: str) -> Dict[str, Any]:
        """Second method with parameter."""
        return {{"param": param, "processed": True}}

    @property
    def data(self):
        """Get data property."""
        return self._data
'''
        elif node["type"] == "function":
            node["code"] = f'''def {node["name"]}():
    """
    {node.get("docstring", "Function documentation")}
    """
    # Function implementation
    result = {{
        "name": "{node["name"]}",
        "type": "function",
        "executed": True
    }}

    # Some processing logic
    if result["executed"]:
        result["status"] = "success"

    return result
'''

    incoming = [e for e in MOCK_GRAPH["edges"] if e["target"] == node_id]
    outgoing = [e for e in MOCK_GRAPH["edges"] if e["source"] == node_id]

    return {
        "node": node,
        "edges": {
            "incoming": [{"source": e["source"], "type": e["type"]} for e in incoming],
            "outgoing": [{"target": e["target"], "type": e["type"]} for e in outgoing]
        }
    }

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main graph visualization page."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codex Aura - Code Dependency Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1e1e1e; color: #ffffff; overflow: hidden; }
        .header { position: absolute; top: 0; left: 0; right: 0; height: 50px; background: #2d2d2d; border-bottom: 1px solid #404040; display: flex; align-items: center; padding: 0 20px; z-index: 1000; }
        .header h1 { margin: 0; font-size: 18px; color: #ffffff; }
        .controls { position: absolute; top: 60px; left: 20px; background: #2d2d2d; border: 1px solid #404040; border-radius: 8px; padding: 15px; min-width: 250px; z-index: 100; }
        .control-group { margin-bottom: 15px; }
        .control-group label { display: block; margin-bottom: 5px; font-weight: bold; color: #cccccc; }
        .control-group select, .control-group input { width: 100%; padding: 5px; background: #1e1e1e; border: 1px solid #404040; border-radius: 4px; color: #ffffff; }
        .graph-container { position: absolute; top: 50px; left: 0; right: 0; bottom: 0; }
        .node-details { position: absolute; top: 60px; right: 20px; width: 350px; background: #2d2d2d; border: 1px solid #404040; border-radius: 8px; padding: 15px; max-height: calc(100vh - 100px); overflow-y: auto; z-index: 100; display: none; }
        .node-details h3 { margin-top: 0; color: #ffffff; }
        .node-details .close-btn { position: absolute; top: 10px; right: 10px; background: none; border: none; color: #cccccc; font-size: 18px; cursor: pointer; }
        .clickable { cursor: pointer; color: #4fc3f7; text-decoration: underline; }
        .clickable:hover { color: #29b6f6; }
        pre { background: #1e1e1e; padding: 10px; border-radius: 4px; overflow-x: auto; border: 1px solid #404040; }
        code { font-family: 'Fira Code', 'Courier New', monospace; }
        .stats { position: absolute; bottom: 20px; left: 20px; background: #2d2d2d; border: 1px solid #404040; border-radius: 8px; padding: 10px; font-size: 12px; z-index: 100; }
        .minimap { position: absolute; bottom: 20px; right: 20px; width: 200px; height: 150px; background: #2d2d2d; border: 1px solid #404040; border-radius: 8px; overflow: hidden; z-index: 100; }
        .minimap svg { width: 100%; height: 100%; }
        .search-results { position: absolute; top: 100px; left: 20px; background: #2d2d2d; border: 1px solid #404040; border-radius: 8px; max-height: 200px; overflow-y: auto; z-index: 100; display: none; }
        .search-result-item { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #404040; }
        .search-result-item:hover { background: #404040; }
        .search-result-item:last-child { border-bottom: none; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Codex Aura - Code Dependency Graph</h1>
    </div>

    <div class="controls">
        <div class="control-group">
            <label for="graph-select">Graph:</label>
            <select id="graph-select">
                <option value="">Select a graph...</option>
            </select>
        </div>

        <div class="control-group">
            <label for="node-filter">Node Types:</label>
            <select id="node-filter" multiple>
                <option value="file" selected>File</option>
                <option value="class" selected>Class</option>
                <option value="function" selected>Function</option>
            </select>
        </div>

        <div class="control-group">
            <label for="edge-filter">Edge Types:</label>
            <select id="edge-filter" multiple>
                <option value="IMPORTS" selected>Imports</option>
                <option value="CALLS" selected>Calls</option>
                <option value="EXTENDS" selected>Extends</option>
            </select>
        </div>

        <div class="control-group">
            <label for="search">Search Nodes:</label>
            <input type="text" id="search" placeholder="Search...">
        </div>

        <button onclick="resetView()">Reset View</button>
    </div>

    <div class="graph-container">
        <svg id="graph-svg"></svg>
    </div>

    <div class="node-details" id="node-details">
        <button class="close-btn" onclick="closeNodeDetails()">&times;</button>
        <h3>Node Details</h3>
        <div id="node-content">
            <p>Select a node to view details</p>
        </div>
    </div>

    <div class="stats" id="stats">
        Nodes: 0 | Edges: 0 | Filtered: 0
    </div>

    <div class="minimap" id="minimap">
        <svg id="minimap-svg"></svg>
    </div>

    <div class="search-results" id="search-results"></div>

    <script>
        let currentGraph = null;
        let svg, g, zoom, simulation;
        let nodes = [], links = [];
        let filteredNodes = [], filteredLinks = [];
        let width, height;
        let minimapSvg, minimapG;

        document.addEventListener('DOMContentLoaded', function() {
            initializeGraph();
            loadGraphs();
        });

        function initializeGraph() {
            const container = document.querySelector('.graph-container');
            width = container.clientWidth;
            height = container.clientHeight;

            svg = d3.select('#graph-svg')
                .attr('width', width)
                .attr('height', height);

            g = svg.append('g');

            zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', function(event) {
                    g.attr('transform', event.transform);
                    updateMinimap();
                });

            svg.call(zoom);

            simulation = d3.forceSimulation()
                .force('link', d3.forceLink().id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(20));

            minimapSvg = d3.select('#minimap-svg')
                .attr('width', 200)
                .attr('height', 150);

            minimapG = minimapSvg.append('g');

            document.getElementById('graph-select').addEventListener('change', loadSelectedGraph);
            document.getElementById('node-filter').addEventListener('change', applyFilters);
            document.getElementById('edge-filter').addEventListener('change', applyFilters);
            document.getElementById('search').addEventListener('input', handleSearch);
        }

        async function loadGraphs() {
            try {
                const response = await fetch('/api/v1/graphs');
                const data = await response.json();

                const select = document.getElementById('graph-select');
                data.graphs.forEach(graph => {
                    const option = document.createElement('option');
                    option.value = graph.id;
                    option.textContent = `${graph.repo_name} (${graph.node_count} nodes, ${graph.edge_count} edges)`;
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Failed to load graphs:', error);
            }
        }

        async function loadSelectedGraph() {
            const graphId = document.getElementById('graph-select').value;
            if (!graphId) return;

            try {
                const response = await fetch(`/api/v1/graph/${graphId}`);
                currentGraph = await response.json();

                nodes = currentGraph.nodes;
                links = currentGraph.edges;

                applyFilters();
            } catch (error) {
                console.error('Failed to load graph:', error);
            }
        }

        function applyFilters() {
            const nodeTypes = Array.from(document.getElementById('node-filter').selectedOptions).map(o => o.value);
            const edgeTypes = Array.from(document.getElementById('edge-filter').selectedOptions).map(o => o.value);

            filteredNodes = nodes.filter(node => nodeTypes.includes(node.type));
            filteredLinks = links.filter(link =>
                edgeTypes.includes(link.type) &&
                filteredNodes.some(n => n.id === link.source) &&
                filteredNodes.some(n => n.id === link.target)
            );

            updateGraph();
        }

        function updateGraph() {
            g.selectAll('*').remove();

            simulation.nodes(filteredNodes);
            simulation.force('link').links(filteredLinks);

            const link = g.append('g')
                .attr('class', 'links')
                .selectAll('line')
                .data(filteredLinks)
                .enter().append('line')
                .attr('stroke', d => getEdgeColor(d.type))
                .attr('stroke-width', 2)
                .attr('stroke-opacity', 0.6);

            const node = g.append('g')
                .attr('class', 'nodes')
                .selectAll('g')
                .data(filteredNodes)
                .enter().append('g')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));

            node.append('circle')
                .attr('r', d => getNodeRadius(d))
                .attr('fill', d => getNodeColor(d.type))
                .attr('stroke', '#fff')
                .attr('stroke-width', 2)
                .on('click', function(event, d) {
                    event.stopPropagation();
                    showNodeDetails(d.id);
                });

            node.append('text')
                .attr('dx', 15)
                .attr('dy', '.35em')
                .text(d => getNodeLabel(d))
                .attr('fill', '#fff')
                .attr('font-size', '12px')
                .attr('pointer-events', 'none');

            simulation.on('tick', function() {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);

                node
                    .attr('transform', d => `translate(${d.x},${d.y})`);
            });

            simulation.alpha(1).restart();

            updateStats();
            updateMinimap();
        }

        function updateStats() {
            const stats = document.getElementById('stats');
            stats.textContent = `Nodes: ${filteredNodes.length} | Edges: ${filteredLinks.length} | Total: ${nodes.length}/${links.length}`;
        }

        function updateMinimap() {
            if (!filteredNodes.length) return;

            minimapG.selectAll('*').remove();

            const bounds = g.node().getBBox();
            const fullWidth = bounds.width;
            const fullHeight = bounds.height;
            const midX = bounds.x + fullWidth / 2;
            const midY = bounds.y + fullHeight / 2;

            const scale = 0.8 / Math.max(fullWidth / 200, fullHeight / 150);
            const translate = [100 - scale * midX, 75 - scale * midY];

            minimapG.attr('transform', `translate(${translate[0]},${translate[1]}) scale(${scale})`);

            minimapG.selectAll('circle')
                .data(filteredNodes)
                .enter().append('circle')
                .attr('cx', d => d.x)
                .attr('cy', d => d.y)
                .attr('r', 2)
                .attr('fill', d => getNodeColor(d.type))
                .attr('opacity', 0.7);

            const transform = d3.zoomTransform(svg.node());
            const viewBounds = {
                x: -transform.x / transform.k,
                y: -transform.y / transform.k,
                width: width / transform.k,
                height: height / transform.k
            };

            minimapG.append('rect')
                .attr('x', viewBounds.x)
                .attr('y', viewBounds.y)
                .attr('width', viewBounds.width)
                .attr('height', viewBounds.height)
                .attr('fill', 'none')
                .attr('stroke', '#4fc3f7')
                .attr('stroke-width', 1 / scale);
        }

        function handleSearch(event) {
            const query = event.target.value.toLowerCase();
            const results = document.getElementById('search-results');

            if (!query) {
                results.style.display = 'none';
                return;
            }

            const matches = filteredNodes.filter(node =>
                node.name.toLowerCase().includes(query) ||
                node.path.toLowerCase().includes(query)
            );

            if (matches.length === 0) {
                results.style.display = 'none';
                return;
            }

            results.innerHTML = '';
            matches.slice(0, 10).forEach(node => {
                const item = document.createElement('div');
                item.className = 'search-result-item';
                item.textContent = `${node.name} (${node.type})`;
                item.onclick = () => {
                    focusOnNode(node.id);
                    results.style.display = 'none';
                    document.getElementById('search').value = '';
                };
                results.appendChild(item);
            });

            results.style.display = 'block';
        }

        function focusOnNode(nodeId) {
            const node = filteredNodes.find(n => n.id === nodeId);
            if (!node) return;

            const transform = d3.zoomIdentity
                .translate(width / 2 - node.x, height / 2 - node.y)
                .scale(1);

            svg.transition().duration(750).call(zoom.transform, transform);
        }

        async function showNodeDetails(nodeId) {
            try {
                const graphId = document.getElementById('graph-select').value;
                const response = await fetch(`/api/v1/graph/${graphId}/node/${nodeId}?include_code=true`);
                const data = await response.json();

                const details = document.getElementById('node-details');
                const content = document.getElementById('node-content');

                const node = data.node;
                const dependencies = data.edges.outgoing.map(e => e.target);
                const dependents = data.edges.incoming.map(e => e.source);

                content.innerHTML = `
                    <h4>${node.name}</h4>
                    <p><strong>Type:</strong> ${node.type}</p>
                    ${node.path ? `<p><strong>Path:</strong> <span class="clickable" onclick="openFile('${node.path}')">${node.path}</span></p>` : ''}
                    ${node.docstring ? `<h5>Docstring:</h5><p>${node.docstring}</p>` : ''}
                    ${node.lines ? `<p><strong>Lines:</strong> ${node.lines[0]}-${node.lines[1]}</p>` : ''}

                    <h5>Dependencies (${dependencies.length}):</h5>
                    <ul>
                        ${dependencies.slice(0, 10).map(dep => `<li>${getNodeName(dep)}</li>`).join('')}
                        ${dependencies.length > 10 ? `<li>... and ${dependencies.length - 10} more</li>` : ''}
                    </ul>

                    <h5>Dependents (${dependents.length}):</h5>
                    <ul>
                        ${dependents.slice(0, 10).map(dep => `<li>${getNodeName(dep)}</li>`).join('')}
                        ${dependents.length > 10 ? `<li>... and ${dependents.length - 10} more</li>` : ''}
                    </ul>

                    ${node.code ? `<h5>Code Preview:</h5><pre><code class="language-python">${escapeHtml(node.code)}</code></pre>` : ''}
                `;

                Prism.highlightAll();

                details.style.display = 'block';
            } catch (error) {
                console.error('Failed to load node details:', error);
            }
        }

        function getNodeName(nodeId) {
            const node = nodes.find(n => n.id === nodeId);
            return node ? node.name : nodeId;
        }

        function openFile(filePath) {
            console.log('Open file:', filePath);
        }

        function closeNodeDetails() {
            document.getElementById('node-details').style.display = 'none';
        }

        function resetView() {
            svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity);
        }

        function getNodeColor(type) {
            const colors = {
                'file': '#4CAF50',
                'class': '#2196F3',
                'function': '#FF9800'
            };
            return colors[type] || '#757575';
        }

        function getEdgeColor(type) {
            const colors = {
                'IMPORTS': '#4CAF50',
                'CALLS': '#2196F3',
                'EXTENDS': '#FF9800'
            };
            return colors[type] || '#757575';
        }

        function getNodeRadius(node) {
            const connections = filteredLinks.filter(l => l.source.id === node.id || l.target.id === node.id).length;
            return Math.max(5, Math.min(15, 5 + Math.sqrt(connections)));
        }

        function getNodeLabel(node) {
            return node.name.length > 20 ? node.name.substring(0, 17) + '...' : node.name;
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

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        window.addEventListener('resize', function() {
            const container = document.querySelector('.graph-container');
            width = container.clientWidth;
            height = container.clientHeight;

            svg.attr('width', width).attr('height', height);
            simulation.force('center', d3.forceCenter(width / 2, height / 2));
            simulation.alpha(1).restart();
        });
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)