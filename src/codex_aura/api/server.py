"""FastAPI server for codex-aura."""

import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator, Field, constr
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager

from ..analyzer.python import PythonAnalyzer
from ..models.graph import Graph, save_graph
from ..storage.sqlite import SQLiteStorage
from ..plugins.registry import PluginRegistry
from ..models.edge import EdgeType
from ..logging import configure_logging, get_logger
from ..middleware import RequestIDMiddleware, RequestLoggingMiddleware
from ..metrics import get_metrics_response, MetricsMiddleware, GRAPHS_TOTAL, GRAPH_SIZE, ANALYSIS_DURATION, ANALYSIS_FILES, CONTEXT_REQUESTS_TOTAL, CONTEXT_NODES_RETURNED
from ..health import health_checker
from ..tracing import configure_tracing, instrument_app, get_tracer
from ..analytics import analytics
from ..search import EmbeddingService, VectorStore, SemanticSearch, HybridSearch
from ..token_budget import BudgetAllocator, BudgetAnalytics, validate_budget_params, get_budget_preset
from ..webhooks import WebhookQueue, WebhookProcessor, set_webhook_processor
from ..webhooks.github import verify_github_signature, extract_github_event, normalize_github_event
from ..webhooks.gitlab import verify_gitlab_signature, extract_gitlab_event, normalize_gitlab_event
from collections import deque

# Configure structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
configure_logging(log_level)
logger = get_logger(__name__)

# Configure tracing
jaeger_host = os.getenv("JAEGER_HOST", "localhost")
jaeger_port = int(os.getenv("JAEGER_PORT", "14268"))
configure_tracing(service_name="codex-aura", jaeger_host=jaeger_host, jaeger_port=jaeger_port)
tracer = get_tracer(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request size."""

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={"error": "Request too large"}
            )
        return await call_next(request)


app = FastAPI(
    title="Codex Aura API",
    description="REST API for code analysis and dependency graph generation",
    version="0.1.0",
    contact={
        "name": "Codex Aura Team",
        "url": "https://github.com/codex-aura/codex-aura",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
)

# Initialize storage
storage = SQLiteStorage()


class GraphUpdater:
    """Updates dependency graphs based on file changes."""

    def __init__(self, storage, analyzer):
        self.storage = storage
        self.analyzer = analyzer

    async def update_files(self, repo_id: str, changed_files: list[str]) -> None:
        """Update graph for repository with changed files."""
        try:
            # Load existing graph
            existing_graph = self.storage.load_graph(repo_id)
            if not existing_graph:
                logger.warning(f"No existing graph found for repo {repo_id}")
                return

            # For now, do a full re-analysis (incremental updates would be more complex)
            # In a real implementation, we'd only re-analyze changed files and their dependencies
            repo_path = Path(existing_graph.repository.path)
            if not repo_path.exists():
                logger.error(f"Repository path {repo_path} no longer exists")
                return

            logger.info(f"Re-analyzing repository {repo_id} due to {len(changed_files)} changed files")

            # Re-analyze the repository
            new_graph = self.analyzer.analyze(repo_path)

            # Generate new graph ID and save
            import uuid
            new_graph_id = f"g_{uuid.uuid4().hex[:12]}"
            self.storage.save_graph(new_graph, new_graph_id)

            logger.info(f"Updated graph for repo {repo_id}: {existing_graph.id} -> {new_graph_id}")

        except Exception as e:
            logger.error(f"Failed to update graph for repo {repo_id}: {e}")
            raise


# Initialize graph updater
graph_updater = GraphUpdater(storage, PythonAnalyzer())

# Initialize webhook components
webhook_queue = WebhookQueue()
webhook_processor = WebhookProcessor(graph_updater=graph_updater)

# Set global webhook processor for arq workers
set_webhook_processor(webhook_processor)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await webhook_queue.initialize()
    logger.info("Webhook queue initialized")

    yield

    # Shutdown
    await webhook_queue.close()
    logger.info("Webhook queue closed")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Add middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(MetricsMiddleware)

# Instrument app for tracing
instrument_app(app)

# Mount static files
import os
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Rate limit exceeded handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "retry_after": exc.retry_after}
    )

# Allowed roots for path traversal protection
ALLOWED_ROOTS = [
    Path.home(),
    Path("/tmp"),
    # Add more as needed
]


def validate_repo_path(path: str) -> Path:
    """Validate repository path with whitelist approach for path traversal protection.

    Args:
        path: The path string to validate

    Returns:
        Resolved Path object if valid

    Raises:
        SecurityError: If path is not in allowed directories
    """
    resolved = Path(path).resolve()

    # Check against allowed roots
    is_allowed = any(
        resolved.is_relative_to(root)
        for root in ALLOWED_ROOTS
    )

    if not is_allowed:
        raise ValueError(f"Path not in allowed directories: {path}")

    return resolved


class AnalyzeRequest(BaseModel):
    """Request model for analyze endpoint."""

    repo_path: constr(max_length=1000) = "."
    edge_types: list[EdgeType] = Field(max_items=10, default=["imports", "calls", "extends"])
    options: dict = {}

    @field_validator("repo_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate repository path for security."""
        path = Path(v).resolve()

        # No path traversal
        if ".." in str(path):
            raise ValueError("Path traversal not allowed")

        # Must exist
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")

        # Must be directory
        if not path.is_dir():
            raise ValueError("Path must be a directory")

        # Additional security check with whitelist
        try:
            validate_repo_path(str(path))
        except Exception as e:
            raise ValueError(f"Security validation failed: {str(e)}")

        return str(path)

    class Config:
        json_schema_extra = {
            "example": {
                "repo_path": "./my-python-project",
                "edge_types": ["imports", "calls"],
                "options": {"exclude_patterns": ["test_*"]}
            }
        }


class AnalyzeResponse(BaseModel):
    """Response model for analyze endpoint."""

    graph_id: str
    status: str
    stats: dict
    duration_ms: int


class GraphInfo(BaseModel):
    """Graph information model."""

    id: str
    repo_name: str
    repo_path: str
    sha: str | None = None
    created_at: datetime
    node_count: int
    edge_count: int


class GraphsResponse(BaseModel):
    """Response model for graphs endpoint."""

    graphs: list[GraphInfo]


class GraphResponse(BaseModel):
    """Response model for graph endpoint."""

    id: str
    repo_name: str
    created_at: str
    nodes: list
    edges: list
    stats: dict


class NodeResponse(BaseModel):
    """Response model for node endpoint."""

    node: dict
    edges: dict


class DependenciesResponse(BaseModel):
    """Response model for dependencies endpoint."""

    root: str
    depth: int
    nodes: list
    edges: list


class ContextRequest(BaseModel):
    """Request model for context endpoint."""

    graph_id: str
    entry_points: list[str]
    depth: int = 2
    include_code: bool = True
    max_nodes: int = 50

    class Config:
        json_schema_extra = {
            "example": {
                "graph_id": "g_abc123def456",
                "entry_points": ["module.main", "module.utils.Helper"],
                "depth": 3,
                "include_code": False,
                "max_nodes": 25
            }
        }

    @field_validator("depth")
    @classmethod
    def validate_depth(cls, v: int) -> int:
        """Validate depth is between 1 and 5."""
        if v < 1 or v > 5:
            raise ValueError("depth must be between 1 and 5")
        return v

    @field_validator("max_nodes")
    @classmethod
    def validate_max_nodes(cls, v: int) -> int:
        """Validate max_nodes is between 1 and 100."""
        if v < 1 or v > 100:
            raise ValueError("max_nodes must be between 1 and 100")
        return v


class ContextNode(BaseModel):
    """Context node model."""

    id: str
    type: str
    path: str
    code: str | None = None
    relevance: float


class ContextResponse(BaseModel):
    """Response model for context endpoint."""

    context_nodes: list[ContextNode]
    total_nodes: int
    truncated: bool


class TokenBudgetedContextRequest(BaseModel):
    """Request model for token-budgeted context endpoint."""

    repo_id: str
    task: str
    entry_points: list[str]
    max_tokens: int
    budget_strategy: str = "greedy"
    model: str = "gpt-4-turbo"

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max_tokens is positive."""
        if v <= 0:
            raise ValueError("max_tokens must be positive")
        return v

    @field_validator("budget_strategy")
    @classmethod
    def validate_budget_strategy(cls, v: str) -> str:
        """Validate budget strategy."""
        valid_strategies = ["greedy", "proportional", "knapsack"]
        if v not in valid_strategies:
            raise ValueError(f"budget_strategy must be one of: {valid_strategies}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "repo_id": "repo_abc123",
                "task": "Fix JWT validation bug",
                "entry_points": ["src/auth/jwt.py"],
                "max_tokens": 8000,
                "budget_strategy": "greedy",
                "model": "gpt-4-turbo"
            }
        }


class TokenBudgetedContextResponse(BaseModel):
    """Response model for token-budgeted context endpoint."""

    context: str
    stats: dict


class AffectedFile(BaseModel):
    """Affected file model for impact analysis."""

    path: str
    impact_type: str  # "direct" or "transitive"
    edges: list[str] | None = None  # For direct impact
    distance: int | None = None  # For transitive impact


class ImpactResponse(BaseModel):
    """Response model for impact analysis endpoint."""

    changed_files: list[str]
    affected_files: list[AffectedFile]
    affected_tests: list[str]


class DeleteGraphResponse(BaseModel):
    """Response model for delete graph endpoint."""

    deleted: bool
    graph_id: str


class SearchRequest(BaseModel):
    """Request model for search endpoint."""

    repo_id: str
    query: str
    mode: str = Field(..., pattern="^(semantic|graph|hybrid)$")
    limit: int = Field(20, ge=1, le=100)
    filters: dict = Field(default_factory=dict)

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: dict) -> dict:
        """Validate filters structure."""
        if not isinstance(v, dict):
            raise ValueError("filters must be a dictionary")

        allowed_keys = {"file_types", "paths"}
        for key in v.keys():
            if key not in allowed_keys:
                raise ValueError(f"Invalid filter key: {key}. Allowed: {allowed_keys}")

        if "file_types" in v and not isinstance(v["file_types"], list):
            raise ValueError("file_types must be a list")

        if "paths" in v and not isinstance(v["paths"], list):
            raise ValueError("paths must be a list")

        return v


class SearchResultItem(BaseModel):
    """Search result item model."""

    fqn: str
    type: str
    file_path: str
    score: float
    snippet: str | None = None


class SearchResponse(BaseModel):
    """Response model for search endpoint."""

    results: list[SearchResultItem]
    total: int
    search_mode: str


@app.get("/health")
async def health():
    """Quick liveness health check endpoint."""
    return health_checker.quick_health()


@app.get("/ready")
async def ready():
    """Readiness check endpoint with basic component checks."""
    return health_checker.readiness_health()


@app.get("/health/deep")
async def deep_health():
    """Deep health check endpoint with comprehensive system analysis."""
    return health_checker.deep_health()


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics_response()




@app.get("/api/v1/info")
async def info():
    """Server information endpoint."""
    return {
        "version": "0.1.0",
        "supported_languages": ["python"],
        "supported_edge_types": ["IMPORTS", "CALLS", "EXTENDS"],
        "storage_backend": "sqlite"
    }


# Webhook endpoints
@app.post("/webhooks/github/{repo_id}")
async def github_webhook(
    repo_id: str,
    request: Request,
    x_hub_signature_256: str = Header(..., alias="X-Hub-Signature-256")
):
    """Handle GitHub webhook events."""
    payload = await request.body()

    # Verify signature
    if not verify_github_signature(payload, x_hub_signature_256):
        raise HTTPException(401, "Invalid signature")

    event = request.headers.get("X-GitHub-Event")
    data = await request.json()

    # Normalize event
    normalized_event = normalize_github_event(event, data)

    # Queue for processing using Redis/arq
    await webhook_queue.enqueue(normalized_event)

    return {"status": "queued"}


@app.post("/webhooks/gitlab/{repo_id}")
async def gitlab_webhook(
    repo_id: str,
    request: Request,
    x_gitlab_token: str = Header(..., alias="X-Gitlab-Token")
):
    """Handle GitLab webhook events."""
    payload = await request.body()

    # Verify signature
    if not verify_gitlab_signature(payload, x_gitlab_token):
        raise HTTPException(401, "Invalid signature")

    event = request.headers.get("X-Gitlab-Event")
    data = await request.json()

    # Normalize event
    normalized_event = normalize_gitlab_event(event, data)

    # Queue for processing using Redis/arq
    await webhook_queue.enqueue(normalized_event)

    return {"status": "queued"}


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
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e1e;
            color: #ffffff;
            overflow: hidden;
        }

        .header {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 50px;
            background: #2d2d2d;
            border-bottom: 1px solid #404040;
            display: flex;
            align-items: center;
            padding: 0 20px;
            z-index: 1000;
        }

        .header h1 {
            margin: 0;
            font-size: 18px;
            color: #ffffff;
        }

        .controls {
            position: absolute;
            top: 60px;
            left: 20px;
            background: #2d2d2d;
            border: 1px solid #404040;
            border-radius: 8px;
            padding: 15px;
            min-width: 250px;
            z-index: 100;
        }

        .control-group {
            margin-bottom: 15px;
        }

        .control-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #cccccc;
        }

        .control-group select, .control-group input {
            width: 100%;
            padding: 5px;
            background: #1e1e1e;
            border: 1px solid #404040;
            border-radius: 4px;
            color: #ffffff;
        }

        .graph-container {
            position: absolute;
            top: 50px;
            left: 0;
            right: 0;
            bottom: 0;
        }

        .node-details {
            position: absolute;
            top: 60px;
            right: 20px;
            width: 350px;
            background: #2d2d2d;
            border: 1px solid #404040;
            border-radius: 8px;
            padding: 15px;
            max-height: calc(100vh - 100px);
            overflow-y: auto;
            z-index: 100;
            display: none;
        }

        .node-details h3 {
            margin-top: 0;
            color: #ffffff;
        }

        .node-details .close-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: none;
            border: none;
            color: #cccccc;
            font-size: 18px;
            cursor: pointer;
        }

        .clickable {
            cursor: pointer;
            color: #4fc3f7;
            text-decoration: underline;
        }

        .clickable:hover {
            color: #29b6f6;
        }

        pre {
            background: #1e1e1e;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            border: 1px solid #404040;
        }

        code {
            font-family: 'Fira Code', 'Courier New', monospace;
        }

        .stats {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: #2d2d2d;
            border: 1px solid #404040;
            border-radius: 8px;
            padding: 10px;
            font-size: 12px;
            z-index: 100;
        }

        .minimap {
            position: absolute;
            bottom: 20px;
            right: 20px;
            width: 200px;
            height: 150px;
            background: #2d2d2d;
            border: 1px solid #404040;
            border-radius: 8px;
            overflow: hidden;
            z-index: 100;
        }

        .minimap svg {
            width: 100%;
            height: 100%;
        }

        .search-results {
            position: absolute;
            top: 100px;
            left: 20px;
            background: #2d2d2d;
            border: 1px solid #404040;
            border-radius: 8px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 100;
            display: none;
        }

        .search-result-item {
            padding: 8px 12px;
            cursor: pointer;
            border-bottom: 1px solid #404040;
        }

        .search-result-item:hover {
            background: #404040;
        }

        .search-result-item:last-child {
            border-bottom: none;
        }
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

        // Initialize
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

            // Add zoom behavior
            zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', function(event) {
                    g.attr('transform', event.transform);
                    updateMinimap();
                });

            svg.call(zoom);

            // Initialize simulation
            simulation = d3.forceSimulation()
                .force('link', d3.forceLink().id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(20));

            // Initialize minimap
            minimapSvg = d3.select('#minimap-svg')
                .attr('width', 200)
                .attr('height', 150);

            minimapG = minimapSvg.append('g');

            // Add event listeners
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
            // Clear previous elements
            g.selectAll('*').remove();

            // Update simulation
            simulation.nodes(filteredNodes);
            simulation.force('link').links(filteredLinks);

            // Create links
            const link = g.append('g')
                .attr('class', 'links')
                .selectAll('line')
                .data(filteredLinks)
                .enter().append('line')
                .attr('stroke', d => getEdgeColor(d.type))
                .attr('stroke-width', 2)
                .attr('stroke-opacity', 0.6);

            // Create nodes
            const node = g.append('g')
                .attr('class', 'nodes')
                .selectAll('g')
                .data(filteredNodes)
                .enter().append('g')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));

            // Add circles
            node.append('circle')
                .attr('r', d => getNodeRadius(d))
                .attr('fill', d => getNodeColor(d.type))
                .attr('stroke', '#fff')
                .attr('stroke-width', 2)
                .on('click', function(event, d) {
                    event.stopPropagation();
                    showNodeDetails(d.id);
                });

            // Add labels
            node.append('text')
                .attr('dx', 15)
                .attr('dy', '.35em')
                .text(d => getNodeLabel(d))
                .attr('fill', '#fff')
                .attr('font-size', '12px')
                .attr('pointer-events', 'none');

            // Update simulation
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

            // Update stats
            updateStats();

            // Update minimap
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

            // Add nodes to minimap
            minimapG.selectAll('circle')
                .data(filteredNodes)
                .enter().append('circle')
                .attr('cx', d => d.x)
                .attr('cy', d => d.y)
                .attr('r', 2)
                .attr('fill', d => getNodeColor(d.type))
                .attr('opacity', 0.7);

            // Add viewport rectangle
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

                    ${node.code ? `<h5>Code Preview:</h5><pre><code class="language-python">${escapeHtml(node.code.slice(0, 500))}</code></pre>` : ''}
                `;

                // Highlight code
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
            // For web interface, we can't directly open files
            // In a real implementation, this might open in an editor or show file content
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
            // Size based on connections
            const connections = filteredLinks.filter(l => l.source.id === node.id || l.target.id === node.id).length;
            return Math.max(5, Math.min(15, 5 + Math.sqrt(connections)));
        }

        function getNodeLabel(node) {
            // Truncate long names
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

        // Handle window resize
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


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
@limiter.limit("10/minute")
async def analyze(request: Request, body: AnalyzeRequest):
    """
    Analyze a repository and generate a dependency graph.

    This endpoint performs static code analysis on a Python repository
    and generates a comprehensive dependency graph showing relationships
    between modules, classes, and functions.

    The analysis includes:
    - Import relationships between modules
    - Function/method calls
    - Class inheritance hierarchies
    - File dependencies

    The generated graph is stored and can be retrieved using the returned graph_id.
    """
    import time
    import uuid

    start_time = time.time()

    with tracer.start_as_current_span("analyze_repository") as span:
        span.set_attribute("repo_path", str(body.repo_path))
        span.set_attribute("edge_types", str(body.edge_types))

        # Repo path is already validated by Pydantic model
        repo_path = Path(body.repo_path)

        try:
            # Analyze repository
            analyzer = PythonAnalyzer()
            graph = analyzer.analyze(repo_path)

            # Generate graph ID
            graph_id = f"g_{uuid.uuid4().hex[:12]}"

            # Save graph to storage
            storage.save_graph(graph, graph_id)

            duration_ms = int((time.time() - start_time) * 1000)
            duration_seconds = duration_ms / 1000.0

            # Update span
            span.set_attribute("graph_id", graph_id)
            span.set_attribute("files_analyzed", graph.stats.node_types.get("file", 0))
            span.set_attribute("duration_ms", duration_ms)

            # Update metrics
            GRAPHS_TOTAL.inc()
            GRAPH_SIZE.labels(graph_id=graph_id).set(len(graph.nodes))
            ANALYSIS_DURATION.labels(repo_name=repo_path.name).observe(duration_seconds)
            ANALYSIS_FILES.labels(repo_name=repo_path.name).inc(graph.stats.node_types.get("file", 0))

            # Track analytics
            analytics.track_analysis(
                repo_path=str(repo_path),
                graph_id=graph_id,
                stats={
                    "files": graph.stats.node_types.get("file", 0),
                    "classes": graph.stats.node_types.get("class", 0),
                    "functions": graph.stats.node_types.get("function", 0),
                    "edges": {
                        "IMPORTS": sum(1 for edge in graph.edges if edge.type == "IMPORTS"),
                        "CALLS": sum(1 for edge in graph.edges if edge.type == "CALLS"),
                        "EXTENDS": sum(1 for edge in graph.edges if edge.type == "EXTENDS"),
                    }
                },
                duration_ms=duration_ms
            )

            # Log successful analysis
            logger.info(
                "analysis_completed",
                graph_id=graph_id,
                repo_path=str(repo_path),
                files_analyzed=graph.stats.node_types.get("file", 0),
                classes_found=graph.stats.node_types.get("class", 0),
                functions_found=graph.stats.node_types.get("function", 0),
                edges_created=len(graph.edges),
                duration_ms=duration_ms
            )

            return AnalyzeResponse(
                graph_id=graph_id,
                status="completed",
                stats={
                    "files": graph.stats.node_types.get("file", 0),
                    "classes": graph.stats.node_types.get("class", 0),
                    "functions": graph.stats.node_types.get("function", 0),
                    "edges": {
                        "IMPORTS": sum(1 for edge in graph.edges if edge.type == "IMPORTS"),
                        "CALLS": sum(1 for edge in graph.edges if edge.type == "CALLS"),
                        "EXTENDS": sum(1 for edge in graph.edges if edge.type == "EXTENDS"),
                    }
                },
                duration_ms=duration_ms
            )

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

            logger.error(
                "analysis_failed",
                repo_path=str(repo_path),
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=int((time.time() - start_time) * 1000)
            )
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/v1/graphs", response_model=GraphsResponse)
async def get_graphs(repo_path: str | None = None):
    """Get list of stored graphs."""
    graphs = storage.list_graphs(repo_path)
    return GraphsResponse(graphs=graphs)


@app.get("/api/v1/graph/{graph_id}", response_model=GraphResponse)
async def get_graph(
    graph_id: str,
    include_code: bool = False,
    node_types: str | None = None,
    edge_types: str | None = None
):
    """
    Retrieve a complete dependency graph.

    Returns the full graph data including all nodes and edges.
    Supports optional filtering by node types and edge types.

    Use include_code=true to include source code in node data (increases response size).
    """
    graph = storage.load_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Apply node type filtering
    filtered_nodes = graph.nodes
    if node_types:
        node_type_list = [t.strip() for t in node_types.split(",")]
        filtered_nodes = [n for n in graph.nodes if n.type in node_type_list]

    # Apply edge type filtering
    filtered_edges = graph.edges
    if edge_types:
        edge_type_list = [t.strip() for t in edge_types.split(",")]
        filtered_edges = [e for e in graph.edges if e.type.value in edge_type_list]

    # Convert nodes to dict format
    nodes_data = []
    for node in filtered_nodes:
        node_dict = node.model_dump()
        if not include_code and "code" in node_dict:
            del node_dict["code"]
        nodes_data.append(node_dict)

    # Convert edges to dict format
    edges_data = [edge.model_dump() for edge in filtered_edges]

    return GraphResponse(
        id=graph_id,
        repo_name=graph.repository.name,
        created_at=graph.generated_at.isoformat(),
        nodes=nodes_data,
        edges=edges_data,
        stats=graph.stats.model_dump()
    )


@app.get("/api/v1/graph/{graph_id}/node/{node_id}", response_model=NodeResponse)
async def get_node(graph_id: str, node_id: str, include_code: bool = False):
    """Get information about a specific node."""
    graph = storage.load_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Find the node
    node = next((n for n in graph.nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Get incoming and outgoing edges
    incoming = [e for e in graph.edges if e.target == node_id]
    outgoing = [e for e in graph.edges if e.source == node_id]

    # Convert node to dict
    node_data = node.model_dump()

    # Add code if requested and available
    if include_code and node.path:
        try:
            repo_path = Path(graph.repository.path)
            file_path = repo_path / node.path
            if file_path.exists() and file_path.is_file():
                with file_path.open("r", encoding="utf-8") as f:
                    node_data["code"] = f.read()
        except Exception as e:
            logger.warning(f"Failed to read code for {node.path}: {e}")

    # Add signature field for functions
    if node.type == "function":
        # Try to extract signature from docstring or code if available
        if node_data.get("code"):
            # Simple signature extraction - could be improved
            try:
                import ast
                tree = ast.parse(node_data["code"])
                for item in ast.walk(tree):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == node.name:
                        # Extract function signature
                        args = []
                        for arg in item.args.args:
                            args.append(arg.arg)
                        if item.args.vararg:
                            args.append(f"*{item.args.vararg.arg}")
                        if item.args.kwarg:
                            args.append(f"**{item.args.kwarg.arg}")
                        node_data["signature"] = f"def {node.name}({', '.join(args)})"
                        break
            except:
                pass
        if "signature" not in node_data:
            node_data["signature"] = f"def {node.name}(...)"  # Placeholder

    edges_data = {
        "incoming": [{"source": e.source, "type": e.type.value} for e in incoming],
        "outgoing": [{"target": e.target, "type": e.type.value} for e in outgoing]
    }

    return NodeResponse(node=node_data, edges=edges_data)


def traverse_dependencies(
    graph: Graph,
    start_node_id: str,
    max_depth: int,
    direction: str,
    edge_types: list[str] | None = None
) -> tuple[set[str], set[tuple[str, str, str]]]:
    """Traverse graph dependencies using BFS.

    Returns:
        Tuple of (node_ids, edges)
    """
    visited = set([start_node_id])
    edges = set()
    queue = deque([(start_node_id, 0)])  # (node_id, depth)

    while queue:
        current_node_id, depth = queue.popleft()

        if depth >= max_depth:
            continue

        # Get edges based on direction
        if direction in ["outgoing", "both"]:
            outgoing = [e for e in graph.edges if e.source == current_node_id]
            if edge_types:
                outgoing = [e for e in outgoing if e.type.value in edge_types]

            for edge in outgoing:
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append((edge.target, depth + 1))
                edges.add((edge.source, edge.target, edge.type.value))

        if direction in ["incoming", "both"]:
            incoming = [e for e in graph.edges if e.target == current_node_id]
            if edge_types:
                incoming = [e for e in incoming if e.type.value in edge_types]

            for edge in incoming:
                if edge.source not in visited:
                    visited.add(edge.source)
                    queue.append((edge.source, depth + 1))
                edges.add((edge.source, edge.target, edge.type.value))

    return visited, edges


@app.get("/api/v1/graph/{graph_id}/dependencies", response_model=DependenciesResponse)
async def get_dependencies(
    graph_id: str,
    node_id: str,
    depth: int = 2,
    direction: str = "both",
    edge_types: str | None = None
):
    """Get dependencies for a node with traversal options."""
    if depth < 1 or depth > 5:
        raise HTTPException(status_code=400, detail="Depth must be between 1 and 5")

    if direction not in ["incoming", "outgoing", "both"]:
        raise HTTPException(status_code=400, detail="Direction must be 'incoming', 'outgoing', or 'both'")

    graph = storage.load_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Check if node exists
    if not any(n.id == node_id for n in graph.nodes):
        raise HTTPException(status_code=404, detail="Node not found")

    # Parse edge types filter
    edge_type_list = None
    if edge_types:
        edge_type_list = [t.strip() for t in edge_types.split(",")]

    # Traverse dependencies
    node_ids, edge_tuples = traverse_dependencies(
        graph, node_id, depth, direction, edge_type_list
    )

    # Get nodes data
    nodes_data = [n.model_dump() for n in graph.nodes if n.id in node_ids]

    # Convert edges to dict format
    edges_data = [
        {"source": src, "target": tgt, "type": typ}
        for src, tgt, typ in edge_tuples
    ]

    return DependenciesResponse(
        root=node_id,
        depth=depth,
        nodes=nodes_data,
        edges=edges_data
    )


@app.post("/api/v1/context", response_model=ContextResponse)
@limiter.limit("60/minute")
async def get_context(request: Request, body: ContextRequest):
    """
    Get contextual nodes around entry points.

    Performs breadth-first search traversal from specified entry points
    to gather relevant context nodes within the specified depth.

    Useful for understanding the code context around specific functions
    or classes, with relevance scoring based on distance from entry points.
    """
    with tracer.start_as_current_span("get_context") as span:
        span.set_attribute("graph_id", body.graph_id)
        span.set_attribute("entry_points", str(body.entry_points))
        span.set_attribute("depth", body.depth)
        span.set_attribute("max_nodes", body.max_nodes)
        span.set_attribute("include_code", body.include_code)

        # Validate depth
        if body.depth < 1 or body.depth > 5:
            raise HTTPException(status_code=400, detail="Depth must be between 1 and 5")

        # Validate max_nodes
        if body.max_nodes < 1 or body.max_nodes > 100:
            raise HTTPException(status_code=400, detail="max_nodes must be between 1 and 100")

        # Load graph
        graph = storage.load_graph(body.graph_id)
        if not graph:
            raise HTTPException(status_code=404, detail="Graph not found")

    # Validate entry points exist
    for entry_point in body.entry_points:
        if not any(n.id == entry_point for n in graph.nodes):
            raise HTTPException(status_code=404, detail=f"Entry point '{entry_point}' not found")

    # Collect all reachable nodes using BFS from all entry points
    all_visited = set()
    node_distances = {}  # node_id -> min_distance

    for entry_point in body.entry_points:
        visited, _ = traverse_dependencies(graph, entry_point, body.depth, "outgoing")
        for node_id in visited:
            if node_id not in all_visited:
                # Calculate distance from nearest entry point
                min_distance = float('inf')
                for ep in body.entry_points:
                    if ep == node_id:
                        min_distance = 0
                        break
                    # BFS to find distance
                    dist = _calculate_distance(graph, ep, node_id, body.depth)
                    if dist is not None:
                        min_distance = min(min_distance, dist)

                if min_distance != float('inf'):
                    node_distances[node_id] = min_distance
                    all_visited.add(node_id)

    # Sort nodes by distance (ascending)
    sorted_nodes = sorted(all_visited, key=lambda n: node_distances.get(n, float('inf')))

    # Apply max_nodes limit
    truncated = len(sorted_nodes) > body.max_nodes
    if truncated:
        sorted_nodes = sorted_nodes[:body.max_nodes]

    # Build context nodes
    context_nodes = []
    for node_id in sorted_nodes:
        node = next(n for n in graph.nodes if n.id == node_id)
        node_dict = node.model_dump()

        context_node = ContextNode(
            id=node.id,
            type=node.type,
            path=node.path,
            code=node_dict.get("code") if body.include_code else None,
            relevance=1.0 / (1 + node_distances.get(node_id, 0))  # Higher relevance for closer nodes
        )
        context_nodes.append(context_node)

        # Update metrics
        CONTEXT_REQUESTS_TOTAL.inc()
        CONTEXT_NODES_RETURNED.labels(truncated=str(truncated).lower()).observe(len(context_nodes))

        # Update span
        span.set_attribute("context_nodes_returned", len(context_nodes))
        span.set_attribute("total_nodes", len(all_visited))
        span.set_attribute("truncated", truncated)

        # Track analytics
        analytics.track_context_request(
            graph_id=body.graph_id,
            entry_points_count=len(body.entry_points),
            depth=body.depth,
            max_nodes=body.max_nodes,
            nodes_returned=len(context_nodes),
            truncated=truncated
        )

        logger.info(
            "context_retrieved",
            graph_id=body.graph_id,
            entry_points=body.entry_points,
            depth=body.depth,
            max_nodes=body.max_nodes,
            context_nodes_returned=len(context_nodes),
            total_nodes=len(all_visited),
            truncated=truncated
        )

        return ContextResponse(
            context_nodes=context_nodes,
            total_nodes=len(all_visited),
            truncated=truncated
        )


@app.post("/api/v1/token-context", response_model=TokenBudgetedContextResponse)
@limiter.limit("30/minute")
async def get_token_budgeted_context(request: Request, body: TokenBudgetedContextRequest):
    """
    Get token-budgeted context for a task.

    Performs intelligent selection and summarization of code context
    within specified token limits using various budget allocation strategies.

    Returns concatenated context string and detailed statistics.
    """
    with tracer.start_as_current_span("get_token_budgeted_context") as span:
        span.set_attribute("repo_id", body.repo_id)
        span.set_attribute("task", body.task)
        span.set_attribute("max_tokens", body.max_tokens)
        span.set_attribute("budget_strategy", body.budget_strategy)
        span.set_attribute("model", body.model)

        # Validate budget parameters
        try:
            validate_budget_params(body.model, body.max_tokens)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Load graph by repo_id (assuming repo_id maps to graph_id)
        # For now, we'll use repo_id as graph_id, but in practice this might need mapping
        graph = storage.load_graph(body.repo_id)
        if not graph:
            raise HTTPException(status_code=404, detail=f"Repository '{body.repo_id}' not found")

        # Validate entry points exist
        for entry_point in body.entry_points:
            if not any(n.id == entry_point for n in graph.nodes):
                raise HTTPException(status_code=404, detail=f"Entry point '{entry_point}' not found")

        # Create ranked nodes from entry points and their dependencies
        # This is a simplified approach - in practice you might want more sophisticated ranking
        all_relevant_nodes = set()
        ranked_nodes = []

        for entry_point in body.entry_points:
            visited, _ = traverse_dependencies(graph, entry_point, 3, "outgoing")  # Get dependencies up to depth 3
            all_relevant_nodes.update(visited)

        # Convert to ranked nodes with basic scoring
        for node_id in all_relevant_nodes:
            node = next(n for n in graph.nodes if n.id == node_id)
            # Simple scoring: entry points get highest score, then by distance
            if node_id in body.entry_points:
                score = 1.0
            else:
                # Calculate min distance from any entry point
                min_distance = float('inf')
                for ep in body.entry_points:
                    dist = _calculate_distance(graph, ep, node_id, 5)
                    if dist is not None:
                        min_distance = min(min_distance, dist)
                score = 1.0 / (1 + min_distance) if min_distance != float('inf') else 0.1

            ranked_nodes.append(type('RankedNode', (), {
                'id': node.id,
                'type': node.type,
                'name': node.name,
                'path': node.path,
                'score': score,
                'content': getattr(node, 'content', ''),
                'signature': getattr(node, 'signature', ''),
                'docstring': getattr(node, 'docstring', '')
            })())

        # Allocate budget
        allocator = BudgetAllocator()
        analytics_tracker = BudgetAnalytics()

        selected_nodes = allocator.allocate(
            ranked_nodes,
            body.max_tokens,
            body.budget_strategy
        )

        # Analyze allocation
        stats = analytics_tracker.analyze_allocation(
            ranked_nodes,
            selected_nodes,
            body.max_tokens,
            body.budget_strategy
        )

        # Build context string
        context_parts = []
        summarizer = None  # Could add summarization if needed

        for node in selected_nodes:
            # Format node content
            node_content = getattr(node, 'content', '')
            signature = getattr(node, 'signature', '')
            docstring = getattr(node, 'docstring', '')

            if signature and node_content:
                context_parts.append(f"# {node.path}\n{signature}\n{node_content}")
            elif docstring:
                context_parts.append(f"# {node.path}\n{docstring}")
            else:
                context_parts.append(f"# {node.path}\n{node_content}")

        context = "\n\n".join(context_parts)

        # Prepare response stats
        response_stats = {
            "total_tokens": stats.total_tokens,
            "budget_used_pct": stats.budget_used_pct,
            "nodes_included": stats.nodes_included,
            "nodes_truncated": stats.nodes_truncated,
            "nodes_excluded": len(ranked_nodes) - stats.nodes_included
        }

        # Update metrics
        CONTEXT_REQUESTS_TOTAL.inc()

        span.set_attribute("context_tokens", stats.total_tokens)
        span.set_attribute("nodes_selected", stats.nodes_included)

        logger.info(
            "token_budgeted_context_generated",
            repo_id=body.repo_id,
            task=body.task[:50],  # Truncate long tasks
            max_tokens=body.max_tokens,
            budget_strategy=body.budget_strategy,
            model=body.model,
            total_tokens=stats.total_tokens,
            budget_used_pct=stats.budget_used_pct,
            nodes_included=stats.nodes_included,
            nodes_excluded=response_stats["nodes_excluded"]
        )

        return TokenBudgetedContextResponse(
            context=context,
            stats=response_stats
        )


@app.get("/api/v1/graph/{graph_id}/impact", response_model=ImpactResponse)
async def get_impact_analysis(graph_id: str, files: str):
    """Analyze impact of changes to specified files."""
    # Parse changed files
    changed_files = [f.strip() for f in files.split(",") if f.strip()]

    if not changed_files:
        raise HTTPException(status_code=400, detail="No files specified")

    # Load graph
    graph = storage.load_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Validate changed files exist in graph
    graph_file_paths = {node.path for node in graph.nodes if node.type == "file"}
    for changed_file in changed_files:
        if changed_file not in graph_file_paths:
            raise HTTPException(status_code=404, detail=f"File '{changed_file}' not found in graph")

    # Find all affected files
    affected_files = []
    affected_file_paths = set()

    # Direct impact: files that directly import/use the changed files
    for changed_file in changed_files:
        # Find all nodes in the changed file
        changed_file_nodes = [n for n in graph.nodes if n.path == changed_file]

        for node in changed_file_nodes:
            # Find incoming edges (who imports/calls this node)
            incoming_edges = [e for e in graph.edges if e.target == node.id]

            for edge in incoming_edges:
                # Find the file containing the source node
                source_node = next((n for n in graph.nodes if n.id == edge.source), None)
                if source_node and source_node.path not in affected_file_paths and source_node.path not in changed_files:
                    affected_file_paths.add(source_node.path)

                    # Collect edge types for this file
                    file_edges = set()
                    for e in incoming_edges:
                        src_node = next((n for n in graph.nodes if n.id == e.source), None)
                        if src_node and src_node.path == source_node.path:
                            file_edges.add(e.type.value)

                    affected_files.append(AffectedFile(
                        path=source_node.path,
                        impact_type="direct",
                        edges=list(file_edges)
                    ))

    # Transitive impact: files affected by the directly affected files (up to depth 3)
    max_transitive_depth = 3
    visited_transitive = set(affected_file_paths)

    for depth in range(1, max_transitive_depth + 1):
        new_affected = set()

        for affected_path in affected_file_paths - set(changed_files):
            if affected_path in visited_transitive:
                # Find nodes in this affected file
                affected_file_nodes = [n for n in graph.nodes if n.path == affected_path]

                for node in affected_file_nodes:
                    # Find incoming edges
                    incoming_edges = [e for e in graph.edges if e.target == node.id]

                    for edge in incoming_edges:
                        source_node = next((n for n in graph.nodes if n.id == edge.source), None)
                        if (source_node and
                            source_node.path not in visited_transitive and
                            source_node.path not in changed_files):

                            new_affected.add(source_node.path)

        # Add new transitive affected files
        for new_path in new_affected:
            affected_files.append(AffectedFile(
                path=new_path,
                impact_type="transitive",
                distance=depth + 1  # +1 because direct is depth 1
            ))

        affected_file_paths.update(new_affected)
        visited_transitive.update(new_affected)

        if not new_affected:
            break

    # Find affected tests
    affected_tests = []
    test_prefixes = ["test_", "tests/", "test/"]

    for affected_path in affected_file_paths:
        # Generate potential test file names
        test_candidates = []

        # Same directory with test_ prefix
        import os
        dir_name = os.path.dirname(affected_path)
        base_name = os.path.basename(affected_path)
        name_without_ext = os.path.splitext(base_name)[0]

        test_candidates.append(os.path.join(dir_name, f"test_{base_name}"))
        test_candidates.append(os.path.join(dir_name, f"test_{name_without_ext}.py"))

        # tests/ directory
        test_candidates.append(os.path.join("tests", base_name))
        test_candidates.append(os.path.join("tests", f"test_{base_name}"))
        test_candidates.append(os.path.join("tests", f"test_{name_without_ext}.py"))

        # Check if any test candidates exist in the graph
        for candidate in test_candidates:
            if any(n.path == candidate for n in graph.nodes if n.type == "file"):
                affected_tests.append(candidate)
                break

    return ImpactResponse(
        changed_files=changed_files,
        affected_files=affected_files,
        affected_tests=affected_tests
    )


def _calculate_distance(graph: Graph, start_node: str, target_node: str, max_depth: int) -> int | None:
    """Calculate shortest path distance between two nodes using BFS."""
    if start_node == target_node:
        return 0

    visited = set([start_node])
    queue = deque([(start_node, 0)])  # (node_id, depth)

    while queue:
        current_node_id, depth = queue.popleft()

        if depth >= max_depth:
            continue

        # Get outgoing edges
        outgoing = [e for e in graph.edges if e.source == current_node_id]

        for edge in outgoing:
            if edge.target == target_node:
                return depth + 1

            if edge.target not in visited:
                visited.add(edge.target)
                queue.append((edge.target, depth + 1))

    return None


@app.get("/api/v1/capabilities")
async def get_capabilities():
    """Get capabilities of all available plugins."""
    return PluginRegistry.get_all_capabilities()


@app.delete("/api/v1/graph/{graph_id}", response_model=DeleteGraphResponse)
async def delete_graph(graph_id: str):
    """Delete a graph from storage."""
    deleted = storage.delete_graph(graph_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Graph not found")

    return DeleteGraphResponse(deleted=True, graph_id=graph_id)


@app.post("/api/v1/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_code(request: Request, body: SearchRequest):
    """
    Search for code using semantic, graph, or hybrid search.

    Performs code search across indexed repositories using different search modes:
    - semantic: Pure semantic similarity search
    - graph: Graph-based structural search
    - hybrid: Combined semantic and graph-based search

    Supports filtering by file types and paths.
    """
    with tracer.start_as_current_span("search_code") as span:
        span.set_attribute("repo_id", body.repo_id)
        span.set_attribute("query", body.query)
        span.set_attribute("mode", body.mode)
        span.set_attribute("limit", body.limit)

        try:
            # Initialize search services
            embedding_service = EmbeddingService()
            vector_store = VectorStore()
            semantic_search = SemanticSearch(embedding_service, vector_store)
            hybrid_search = HybridSearch(semantic_search)

            results = []

            if body.mode == "semantic":
                # Semantic search
                search_results = await semantic_search.search(
                    repo_id=body.repo_id,
                    query=body.query,
                    limit=body.limit * 2  # Get more for filtering
                )

                for result in search_results:
                    chunk = result.chunk
                    # Apply filters
                    if _matches_filters(chunk, body.filters):
                        snippet = _extract_snippet(chunk.content)
                        fqn = f"{chunk.file_path}::{chunk.name}" if chunk.type != "file" else chunk.file_path

                        results.append(SearchResultItem(
                            fqn=fqn,
                            type=chunk.type,
                            file_path=chunk.file_path,
                            score=result.score,
                            snippet=snippet
                        ))

            elif body.mode == "graph":
                # Graph-based search (simplified - search by name/path)
                graph = storage.load_graph(body.repo_id)
                if not graph:
                    raise HTTPException(status_code=404, detail="Repository graph not found")

                # Simple text-based search in graph nodes
                query_lower = body.query.lower()
                matching_nodes = []

                for node in graph.nodes:
                    if _matches_filters({"file_path": node.path, "type": node.type}, body.filters):
                        # Search in node name, path, or content
                        searchable_text = f"{node.name} {node.path}".lower()
                        if query_lower in searchable_text:
                            matching_nodes.append(node)

                # Sort by relevance (simple scoring)
                matching_nodes.sort(key=lambda n: len(n.name) if body.query.lower() in n.name.lower() else 0, reverse=True)

                for node in matching_nodes[:body.limit]:
                    fqn = node.path if node.type == "file" else node.id
                    snippet = _extract_snippet_from_node(node)

                    results.append(SearchResultItem(
                        fqn=fqn,
                        type=node.type,
                        file_path=node.path,
                        score=0.8,  # Fixed score for graph search
                        snippet=snippet
                    ))

            elif body.mode == "hybrid":
                # Hybrid search
                ranked_nodes = await hybrid_search.search(
                    repo_id=body.repo_id,
                    task=body.query,
                    entry_points=[],  # Empty for general search
                    depth=2
                )

                for ranked_node in ranked_nodes[:body.limit]:
                    # Parse fqn to get file_path and name
                    if "::" in ranked_node.fqn:
                        file_path, name = ranked_node.fqn.split("::", 1)
                        node_type = "function"  # Assume function if has name
                    else:
                        file_path = ranked_node.fqn
                        name = ""
                        node_type = "file"

                    # Apply filters
                    if _matches_filters({"file_path": file_path, "type": node_type}, body.filters):
                        results.append(SearchResultItem(
                            fqn=ranked_node.fqn,
                            type=node_type,
                            file_path=file_path,
                            score=ranked_node.score,
                            snippet=None  # No snippet for hybrid search
                        ))

            # Limit results
            results = results[:body.limit]

            # Update metrics
            CONTEXT_REQUESTS_TOTAL.inc()  # Reuse existing metric

            span.set_attribute("results_count", len(results))

            logger.info(
                "search_completed",
                repo_id=body.repo_id,
                query=body.query,
                mode=body.mode,
                results_count=len(results)
            )

            return SearchResponse(
                results=results,
                total=len(results),
                search_mode=body.mode
            )

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

            logger.error(
                "search_failed",
                repo_id=body.repo_id,
                query=body.query,
                mode=body.mode,
                error=str(e)
            )
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


def _matches_filters(chunk: dict, filters: dict) -> bool:
    """Check if chunk matches the given filters."""
    # File types filter
    if "file_types" in filters:
        file_types = filters["file_types"]
        if file_types:
            file_path = chunk.get("file_path", "")
            file_ext = file_path.split(".")[-1] if "." in file_path else ""
            if f".{file_ext}" not in file_types:
                return False

    # Paths filter
    if "paths" in filters:
        paths = filters["paths"]
        if paths:
            file_path = chunk.get("file_path", "")
            if not any(path in file_path for path in paths):
                return False

    return True


def _extract_snippet(content: str, max_length: int = 100) -> str:
    """Extract a code snippet from content."""
    if len(content) <= max_length:
        return content

    # Try to cut at a reasonable boundary
    truncated = content[:max_length]
    last_newline = truncated.rfind('\n')
    if last_newline > max_length * 0.7:
        return truncated[:last_newline]

    return truncated + "..."


def _extract_snippet_from_node(node) -> str | None:
    """Extract snippet from a graph node."""
    # Try to get code from node if available
    if hasattr(node, 'code') and node.code:
        return _extract_snippet(node.code)

    # Fallback to docstring or name
    if hasattr(node, 'docstring') and node.docstring:
        return _extract_snippet(node.docstring)

    return f"{node.type}: {node.name}"


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