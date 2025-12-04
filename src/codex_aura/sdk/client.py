"""Codex Aura Python SDK client."""

import uuid
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..analyzer.python import PythonAnalyzer
from ..storage.sqlite import SQLiteStorage
from ..models.graph import Graph
from .context import Context, ContextNode
from .impact import ImpactAnalysis, AffectedFile
from .exceptions import CodexAuraError, ConnectionError, AnalysisError, ValidationError, TimeoutError


class CodexAura:
    """Main Codex Aura SDK client.

    Supports both local and remote modes for code analysis and context generation.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        repo_path: Optional[Union[str, Path]] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        db_path: str = "codex_aura.db"
    ):
        """Initialize Codex Aura client.

        Args:
            server_url: URL of remote Codex Aura server (remote mode)
            repo_path: Path to local repository (local mode)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            db_path: Path to local database file for storing graphs

        Raises:
            ValidationError: If neither server_url nor repo_path is provided
        """
        if not server_url and not repo_path:
            raise ValidationError("Either server_url or repo_path must be provided")

        self.server_url = server_url.rstrip('/') if server_url else None
        self.repo_path = Path(repo_path) if repo_path else None
        self.timeout = timeout
        self.max_retries = max_retries
        self.db_path = db_path

        # Initialize components
        if self.repo_path:
            self.analyzer = PythonAnalyzer()
            self.storage = SQLiteStorage(db_path)

        # Setup HTTP client for remote mode
        if self.server_url:
            self._setup_http_client()

    def _setup_http_client(self):
        """Setup HTTP client with retry logic."""
        self.session = requests.Session()

        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update({
            'User-Agent': 'CodexAura-SDK/0.1.0',
            'Content-Type': 'application/json'
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to server with error handling."""
        if not self.server_url:
            raise ValidationError("Server URL not configured")

        url = urljoin(self.server_url + '/', endpoint.lstrip('/'))

        try:
            kwargs.setdefault('timeout', self.timeout)
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Failed to connect to server: {self.server_url}")
        except requests.exceptions.HTTPError as e:
            raise CodexAuraError(f"HTTP error {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    def analyze(self, repo_path: Optional[Union[str, Path]] = None) -> str:
        """Analyze repository and generate dependency graph.

        Args:
            repo_path: Repository path (only for local mode, overrides instance repo_path)

        Returns:
            Graph ID for the generated graph

        Raises:
            ValidationError: If repo_path not provided in local mode
            AnalysisError: If analysis fails
        """
        if self.server_url:
            # Remote mode
            target_path = repo_path or self.repo_path
            if not target_path:
                raise ValidationError("repo_path required for remote analysis")

            data = {
                "repo_path": str(target_path),
                "edge_types": ["imports", "calls", "extends"],
                "options": {}
            }

            try:
                response = self._make_request("POST", "/api/v1/analyze", json=data)
                return response["graph_id"]
            except Exception as e:
                raise AnalysisError(f"Remote analysis failed: {str(e)}")

        else:
            # Local mode
            target_path = Path(repo_path) if repo_path else self.repo_path
            if not target_path:
                raise ValidationError("repo_path required for local analysis")

            if not target_path.exists() or not target_path.is_dir():
                raise ValidationError(f"Repository path does not exist or is not a directory: {target_path}")

            try:
                start_time = time.time()
                graph = self.analyzer.analyze(target_path)
                duration_ms = int((time.time() - start_time) * 1000)

                # Generate graph ID and save
                graph_id = f"g_{uuid.uuid4().hex[:12]}"
                self.storage.save_graph(graph, graph_id)

                return graph_id

            except Exception as e:
                raise AnalysisError(f"Local analysis failed: {str(e)}")

    def get_context(
        self,
        task: str,
        entry_points: List[str],
        graph_id: Optional[str] = None,
        depth: int = 2,
        max_tokens: int = 8000,
        include_code: bool = True
    ) -> Context:
        """Get contextual information around entry points.

        Args:
            task: Description of the task (for future use)
            entry_points: List of entry point identifiers
            graph_id: Graph ID to use (auto-detects latest if not provided)
            depth: Traversal depth from entry points
            max_tokens: Maximum tokens for context (for future use)
            include_code: Whether to include source code in context

        Returns:
            Context object with relevant nodes and relationships

        Raises:
            ValidationError: If entry_points is empty
            AnalysisError: If context retrieval fails
        """
        if not entry_points:
            raise ValidationError("entry_points cannot be empty")

        if self.server_url:
            # Remote mode
            if not graph_id:
                # Try to find latest graph for current repo
                graphs = self._make_request("GET", "/api/v1/graphs")
                if not graphs["graphs"]:
                    raise ValidationError("No graphs found. Run analyze() first.")
                graph_id = graphs["graphs"][0]["id"]

            data = {
                "graph_id": graph_id,
                "entry_points": entry_points,
                "depth": depth,
                "include_code": include_code,
                "max_nodes": min(100, max(1, max_tokens // 100))  # Rough estimation
            }

            try:
                response = self._make_request("POST", "/api/v1/context", json=data)
                return Context.from_api_response(response)
            except Exception as e:
                raise AnalysisError(f"Remote context retrieval failed: {str(e)}")

        else:
            # Local mode
            if not graph_id:
                # Find latest graph
                graphs = self.storage.list_graphs()
                if not graphs:
                    raise ValidationError("No graphs found. Run analyze() first.")
                graph_id = graphs[0]["id"]

            graph = self.storage.load_graph(graph_id)
            if not graph:
                raise ValidationError(f"Graph {graph_id} not found")

            # Validate entry points exist
            for entry_point in entry_points:
                if not any(n.id == entry_point for n in graph.nodes):
                    raise ValidationError(f"Entry point '{entry_point}' not found in graph")

            # Simple context extraction (simplified version of server logic)
            context_nodes = []
            visited = set()

            for entry_point in entry_points:
                if entry_point not in visited:
                    visited.add(entry_point)
                    # Add the entry point node
                    node = next(n for n in graph.nodes if n.id == entry_point)
                    context_nodes.append(ContextNode(
                        id=node.id,
                        type=node.type,
                        path=node.path,
                        code=None,  # Simplified: no code storage in local mode
                        relevance=1.0
                    ))

                    # Add directly connected nodes (simplified)
                    connected_nodes = set()
                    for edge in graph.edges:
                        if edge.source == entry_point and edge.target not in visited:
                            connected_nodes.add(edge.target)
                        elif edge.target == entry_point and edge.source not in visited:
                            connected_nodes.add(edge.source)

                    for node_id in connected_nodes:
                        if len(context_nodes) >= 50:  # Limit
                            break
                        visited.add(node_id)
                        node = next(n for n in graph.nodes if n.id == node_id)
                        context_nodes.append(ContextNode(
                            id=node.id,
                            type=node.type,
                            path=node.path,
                            code=None,  # Simplified: no code storage in local mode
                            relevance=0.8
                        ))

            return Context(
                context_nodes=context_nodes,
                total_nodes=len(visited),
                truncated=len(context_nodes) >= 50
            )

    def analyze_impact(self, changed_files: List[str], graph_id: Optional[str] = None) -> ImpactAnalysis:
        """Analyze impact of changes to specified files.

        Args:
            changed_files: List of changed file paths
            graph_id: Graph ID to use (auto-detects latest if not provided)

        Returns:
            ImpactAnalysis object with affected files and tests

        Raises:
            ValidationError: If changed_files is empty
            AnalysisError: If impact analysis fails
        """
        if not changed_files:
            raise ValidationError("changed_files cannot be empty")

        if self.server_url:
            # Remote mode
            if not graph_id:
                graphs = self._make_request("GET", "/api/v1/graphs")
                if not graphs["graphs"]:
                    raise ValidationError("No graphs found. Run analyze() first.")
                graph_id = graphs["graphs"][0]["id"]

            files_param = ",".join(changed_files)
            try:
                response = self._make_request("GET", f"/api/v1/graph/{graph_id}/impact", params={"files": files_param})
                return ImpactAnalysis.from_api_response(response)
            except Exception as e:
                raise AnalysisError(f"Remote impact analysis failed: {str(e)}")

        else:
            # Local mode - simplified implementation
            if not graph_id:
                graphs = self.storage.list_graphs()
                if not graphs:
                    raise ValidationError("No graphs found. Run analyze() first.")
                graph_id = graphs[0]["id"]

            graph = self.storage.load_graph(graph_id)
            if not graph:
                raise ValidationError(f"Graph {graph_id} not found")

            # Simplified impact analysis
            affected_files = []
            affected_file_paths = set()

            # Direct impact: files that import from changed files
            for changed_file in changed_files:
                changed_file_nodes = [n for n in graph.nodes if n.path == changed_file]

                for node in changed_file_nodes:
                    incoming_edges = [e for e in graph.edges if e.target == node.id]

                    for edge in incoming_edges:
                        source_node = next((n for n in graph.nodes if n.id == edge.source), None)
                        if source_node and source_node.path not in affected_file_paths and source_node.path not in changed_files:
                            affected_file_paths.add(source_node.path)
                            affected_files.append({
                                "path": source_node.path,
                                "impact_type": "direct",
                                "edges": [edge.type.value]
                            })

            # Find affected tests
            affected_tests = []
            test_prefixes = ["test_", "tests/"]

            for affected_path in affected_file_paths:
                for prefix in test_prefixes:
                    if prefix in affected_path:
                        affected_tests.append(affected_path)
                        break

            return ImpactAnalysis(
                changed_files=changed_files,
                affected_files=[{
                    "path": f["path"],
                    "impact_type": f["impact_type"],
                    "edges": f.get("edges"),
                    "distance": f.get("distance")
                } for f in affected_files],
                affected_tests=affected_tests
            )

    def list_graphs(self) -> List[Dict[str, Any]]:
        """List available graphs.

        Returns:
            List of graph information dictionaries
        """
        if self.server_url:
            response = self._make_request("GET", "/api/v1/graphs")
            return response["graphs"]
        else:
            return self.storage.list_graphs()

    def delete_graph(self, graph_id: str) -> bool:
        """Delete a graph.

        Args:
            graph_id: Graph ID to delete

        Returns:
            True if deleted successfully
        """
        if self.server_url:
            try:
                response = self._make_request("DELETE", f"/api/v1/graph/{graph_id}")
                return response.get("deleted", False)
            except Exception:
                return False
        else:
            return self.storage.delete_graph(graph_id)