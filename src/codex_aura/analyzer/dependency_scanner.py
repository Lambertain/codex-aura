"""Multi-repo dependency scanner for finding service-to-service relationships."""

import re
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass

from .base import BaseAnalyzer
from ..models.graph import Graph
from ..models.node import Node
from ..models.edge import Edge, EdgeType
from ..storage.service_registry import ServiceRegistry
from ..storage.sqlite import SQLiteStorage


@dataclass
class ServiceDependency:
    """Represents a dependency between services."""
    source_service: str
    target_service: str
    dependency_type: str  # 'http', 'grpc', 'kafka', 'import'
    line_number: Optional[int] = None
    context: Optional[str] = None


class MultiRepoDependencyScanner(BaseAnalyzer):
    """Scans multiple repositories for inter-service dependencies.

    Analyzes code across repositories to find:
    - HTTP calls (requests.get, urllib, etc.)
    - gRPC client calls
    - Kafka topic usage
    - Import-like references to other services
    """

    def __init__(self, service_registry: Optional[ServiceRegistry] = None):
        self.service_registry = service_registry
        # Python patterns
        self.python_patterns = {
            'http': [
                r'requests\.(get|post|put|delete|patch)\(["\']([^"\']*?)["\']',
                r'urllib\.request\.urlopen\(["\']([^"\']*?)["\']',
                r'httpx\.(get|post|put|delete|patch)\(["\']([^"\']*?)["\']',
                r'fetch\(["\']([^"\']*?)["\']',  # aiohttp
            ],
            'grpc': [
                r'grpc\.client\.stub\(["\']([^"\']*?)["\']',
                r'\.stub\(["\']([^"\']*?)["\']',
                r'grpc\.aio\.secure_channel\(["\']([^"\']*?)["\']',
                r'grpc\.aio\.insecure_channel\(["\']([^"\']*?)["\']',
            ],
            'kafka': [
                r'KafkaProducer.*topic=["\']([^"\']*?)["\']',
                r'KafkaConsumer.*topic=["\']([^"\']*?)["\']',
                r'\.send\(.*topic=["\']([^"\']*?)["\']',
                r'\.subscribe\(\["\']([^"\']*?)["\']',
                r'producer\.send\(["\']([^"\']*?)["\']',
                r'consumer\.subscribe\(\["\']([^"\']*?)["\']',
            ],
            'import': [
                r'import\s+([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)',
                r'from\s+([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\s+import',
            ]
        }

        # TypeScript/JavaScript patterns
        self.typescript_patterns = {
            'http': [
                r'fetch\(["\']([^"\']*?)["\']',
                r'axios\.(get|post|put|delete|patch)\(["\']([^"\']*?)["\']',
                r'http\.(get|post|put|delete|patch)\(["\']([^"\']*?)["\']',
            ],
            'grpc': [
                r'grpc\.client\(["\']([^"\']*?)["\']',
                r'new\s+grpc\.Client\(["\']([^"\']*?)["\']',
            ],
            'kafka': [
                r'producer\.send\(["\']([^"\']*?)["\']',
                r'consumer\.subscribe\(\["\']([^"\']*?)["\']',
                r'kafka\.producer.*topic:\s*["\']([^"\']*?)["\']',
                r'kafka\.consumer.*topic:\s*["\']([^"\']*?)["\']',
            ],
            'import': [
                r'import\s+.*from\s+["\']([^"\']*?)["\']',
                r'import\s*\*\s+as\s+.*from\s+["\']([^"\']*?)["\']',
            ]
        }

        self.service_patterns = {
            '.py': self.python_patterns,
            '.ts': self.typescript_patterns,
            '.js': self.typescript_patterns,
            '.tsx': self.typescript_patterns,
            '.jsx': self.typescript_patterns,
        }

    def analyze(self, repo_ids: List[str], repo_paths: Optional[List[Path]] = None) -> Graph:
        """Analyze multiple repositories for inter-service dependencies.

        Args:
            repo_ids: List of repository IDs.
            repo_paths: Optional list of paths to repository root directories.
                        If None, assumes repositories are not available locally.

        Returns:
            Graph containing service nodes and dependency edges.
        """
        all_dependencies = []
        service_nodes = []

        for i, repo_id in enumerate(repo_ids):
            # Get service name from registry
            service_name = None
            if self.service_registry:
                service_name = self.service_registry.get_service_name_by_repo_id(repo_id)

            if not service_name:
                # Fallback to repo_id if no service registered
                service_name = repo_id

            service_node = Node(
                id=f"service_{service_name}",
                type="service",
                name=service_name,
                path=repo_id  # Store repo_id in path field
            )
            service_nodes.append(service_node)

            # Analyze files if paths are provided
            if repo_paths and i < len(repo_paths):
                repo_path = repo_paths[i]
                # Analyze all supported file types
                for ext in self.service_patterns.keys():
                    files = list(repo_path.rglob(f"*{ext}"))
                    for file_path in files:
                        deps = self._analyze_file_dependencies(file_path, service_name)
                        all_dependencies.extend(deps)

        # Create edges from dependencies
        edges = []
        for dep in all_dependencies:
            source_id = f"service_{dep.source_service}"
            target_id = f"service_{dep.target_service}"

            # Only create edge if both services exist
            if any(n.id == source_id for n in service_nodes) and \
               any(n.id == target_id for n in service_nodes):
                edge = Edge(
                    source=source_id,
                    target=target_id,
                    type=EdgeType.SERVICE_CALLS,
                    line=dep.line_number
                )
                edges.append(edge)

        return Graph(nodes=service_nodes, edges=edges)

    def analyze_file(self, file_path: Path) -> List[Node]:
        """Not used for multi-repo scanning - returns empty list."""
        return []

    def resolve_references(self, node: Node) -> List["Reference"]:
        """Not used for multi-repo scanning - returns empty list."""
        return []

    def _analyze_file_dependencies(self, file_path: Path, source_repo: str) -> List[ServiceDependency]:
        """Analyze a single file for service dependencies.

        Args:
            file_path: Path to the file to analyze.
            source_repo: Name of the repository containing this file.

        Returns:
            List of ServiceDependency objects found in the file.
        """
        dependencies = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, FileNotFoundError):
            return dependencies

        # Get patterns based on file extension
        file_ext = file_path.suffix
        patterns = self.service_patterns.get(file_ext, self.python_patterns)  # fallback to python

        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            for dep_type, type_patterns in patterns.items():
                for pattern in type_patterns:
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        target = self._extract_service_name(match, dep_type, file_ext)
                        if target and target != source_repo:
                            dep = ServiceDependency(
                                source_service=source_repo,
                                target_service=target,
                                dependency_type=dep_type,
                                line_number=line_num,
                                context=line.strip()
                            )
                            dependencies.append(dep)

        return dependencies

    def _extract_service_name(self, match: re.Match, dep_type: str, file_ext: str) -> Optional[str]:
        """Extract service name from regex match.

        Args:
            match: Regex match object.
            dep_type: Type of dependency ('http', 'grpc', 'kafka', 'import').
            file_ext: File extension ('.py', '.ts', etc.).

        Returns:
            Service name or None if cannot be determined.
        """
        try:
            if dep_type == 'http':
                # Extract domain/service from URL
                url_group = 2 if file_ext in ['.py'] else 1  # Different group for different patterns
                if len(match.groups()) >= url_group:
                    url = match.group(url_group)
                    if '://' in url:
                        domain = url.split('://')[1].split('/')[0]
                        # Simple heuristic: if domain contains service-like names
                        if any(keyword in domain.lower() for keyword in ['api', 'service', 'svc', 'gateway']):
                            return domain.split('.')[0]
                        # Check for localhost patterns like service-name:port
                        if ':' in domain and not domain.startswith('localhost'):
                            return domain.split(':')[0]

            elif dep_type == 'grpc':
                # gRPC typically uses service names directly
                if len(match.groups()) >= 1:
                    service_name = match.group(1)
                    # Clean up common patterns
                    service_name = service_name.replace('grpc://', '').replace('grpcs://', '')
                    if ':' in service_name:
                        service_name = service_name.split(':')[0]
                    return service_name

            elif dep_type == 'kafka':
                # Kafka topics often follow service-topic pattern
                if len(match.groups()) >= 1:
                    topic = match.group(1)
                    # Common patterns: service-topic, service.topic, service_topic
                    for separator in ['-', '.', '_']:
                        if separator in topic:
                            service_part = topic.split(separator)[0]
                            if service_part and len(service_part) > 2:  # Avoid very short names
                                return service_part
                    # If no separator, check if it's a known service topic
                    return topic

            elif dep_type == 'import':
                # Import statements might reference other services
                if file_ext == '.py':
                    if len(match.groups()) >= 2:
                        module = match.group(1)
                        submodule = match.group(2)
                        # Check for service-like imports
                        if module in ['api', 'client', 'service', 'grpc', 'kafka']:
                            return submodule
                        elif submodule in ['api', 'client', 'service']:
                            return module
                else:  # TypeScript/JavaScript
                    if len(match.groups()) >= 1:
                        import_path = match.group(1)
                        # Check for @service-name/ patterns or service-name imports
                        if import_path.startswith('@'):
                            service_name = import_path.split('/')[0][1:]  # Remove @
                            return service_name
                        elif '/' in import_path and not import_path.startswith('.'):
                            service_name = import_path.split('/')[0]
                            return service_name

        except IndexError:
            # If group doesn't exist, skip
            pass

        return None