"""Tests for multi-repo dependency scanner."""

import pytest
import tempfile
from pathlib import Path

from ..src.codex_aura.analyzer.dependency_scanner import MultiRepoDependencyScanner, ServiceDependency
from ..src.codex_aura.models.graph import Graph
from ..src.codex_aura.models.node import Node
from ..src.codex_aura.models.edge import Edge, EdgeType


class TestMultiRepoDependencyScanner:
    """Test cases for MultiRepoDependencyScanner."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scanner = MultiRepoDependencyScanner()

    def test_extract_service_name_http_python(self):
        """Test HTTP service name extraction for Python."""
        from ..src.codex_aura.analyzer.dependency_scanner import MultiRepoDependencyScanner
        scanner = MultiRepoDependencyScanner()

        # Test HTTP URL extraction
        import re
        pattern = r'requests\.(get|post|put|delete|patch)\(["\']([^"\']*?)["\']'
        match = re.search(pattern, 'requests.get("http://api-service:8080/users")')
        result = scanner._extract_service_name(match, 'http', '.py')
        assert result == 'api-service'

    def test_extract_service_name_grpc_python(self):
        """Test gRPC service name extraction for Python."""
        scanner = MultiRepoDependencyScanner()

        import re
        pattern = r'grpc\.client\.stub\(["\']([^"\']*?)["\']'
        match = re.search(pattern, 'grpc.client.stub("user-service:50051")')
        result = scanner._extract_service_name(match, 'grpc', '.py')
        assert result == 'user-service'

    def test_extract_service_name_kafka_python(self):
        """Test Kafka topic service name extraction for Python."""
        scanner = MultiRepoDependencyScanner()

        import re
        pattern = r'\.send\(.*topic=["\']([^"\']*?)["\']'
        match = re.search(pattern, 'producer.send(topic="order-events")')
        result = scanner._extract_service_name(match, 'kafka', '.py')
        assert result == 'order'

    def test_analyze_file_dependencies_python(self):
        """Test analyzing Python file for dependencies."""
        scanner = MultiRepoDependencyScanner()

        # Create temporary Python file with dependencies
        python_content = '''
import requests
import grpc

def get_users():
    response = requests.get("http://user-service:8080/api/users")
    return response.json()

def create_order():
    # gRPC call
    stub = grpc.client.stub("order-service:50051")
    return stub.CreateOrder(order_data)

def send_notification():
    producer.send(topic="notification-events", value=message)
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(python_content)
            temp_file = Path(f.name)

        try:
            dependencies = scanner._analyze_file_dependencies(temp_file, "web-app")

            # Should find 3 dependencies
            assert len(dependencies) == 3

            # Check HTTP dependency
            http_dep = next(d for d in dependencies if d.dependency_type == 'http')
            assert http_dep.source_service == "web-app"
            assert http_dep.target_service == "user-service"

            # Check gRPC dependency
            grpc_dep = next(d for d in dependencies if d.dependency_type == 'grpc')
            assert grpc_dep.source_service == "web-app"
            assert grpc_dep.target_service == "order-service"

            # Check Kafka dependency
            kafka_dep = next(d for d in dependencies if d.dependency_type == 'kafka')
            assert kafka_dep.source_service == "web-app"
            assert kafka_dep.target_service == "notification"

        finally:
            temp_file.unlink()

    def test_analyze_file_dependencies_typescript(self):
        """Test analyzing TypeScript file for dependencies."""
        scanner = MultiRepoDependencyScanner()

        # Create temporary TypeScript file with dependencies
        ts_content = '''
import axios from 'axios';
import * as grpc from '@grpc/grpc-js';

async function getUsers() {
    const response = await axios.get('http://user-service:8080/api/users');
    return response.data;
}

function createOrder() {
    const client = new grpc.Client('order-service:50051', grpc.credentials.createInsecure());
    return client;
}

function sendNotification() {
    producer.send({
        topic: 'notification-events',
        messages: [message]
    });
}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
            f.write(ts_content)
            temp_file = Path(f.name)

        try:
            dependencies = scanner._analyze_file_dependencies(temp_file, "web-app")

            # Should find dependencies
            http_deps = [d for d in dependencies if d.dependency_type == 'http']
            grpc_deps = [d for d in dependencies if d.dependency_type == 'grpc']
            kafka_deps = [d for d in dependencies if d.dependency_type == 'kafka']

            assert len(http_deps) >= 1
            assert len(grpc_deps) >= 1
            assert len(kafka_deps) >= 1

        finally:
            temp_file.unlink()

    def test_analyze_multiple_repos(self):
        """Test analyzing multiple repositories."""
        scanner = MultiRepoDependencyScanner()

        # Create temporary directories for repos
        with tempfile.TemporaryDirectory() as temp_dir:
            repo1_path = Path(temp_dir) / "repo1"
            repo2_path = Path(temp_dir) / "repo2"
            repo3_path = Path(temp_dir) / "repo3"

            repo1_path.mkdir()
            repo2_path.mkdir()
            repo3_path.mkdir()

            # Create files with cross-repo dependencies
            (repo1_path / "api.py").write_text('''
import requests
response = requests.get("http://repo2-service:8080/data")
''')

            (repo2_path / "grpc_client.py").write_text('''
import grpc
stub = grpc.client.stub("repo3-service:50051")
''')

            (repo3_path / "kafka_producer.py").write_text('''
producer.send(topic="repo1-events", value=data)
''')

            repos = [repo1_path, repo2_path, repo3_path]
            graph = scanner.analyze(repos)

            # Should have 3 service nodes
            assert len(graph.nodes) == 3
            service_names = {node.name for node in graph.nodes}
            assert service_names == {"repo1", "repo2", "repo3"}

            # Should have dependency edges
            assert len(graph.edges) > 0

            # Check that edges are SERVICE_CALLS type
            for edge in graph.edges:
                assert edge.type == EdgeType.SERVICE_CALLS

    def test_service_dependency_creation(self):
        """Test ServiceDependency object creation."""
        dep = ServiceDependency(
            source_service="web-app",
            target_service="api-service",
            dependency_type="http",
            line_number=10,
            context="requests.get('http://api-service:8080/users')"
        )

        assert dep.source_service == "web-app"
        assert dep.target_service == "api-service"
        assert dep.dependency_type == "http"
        assert dep.line_number == 10
        assert "api-service" in dep.context


class TestDependencyScanService:
    """Test cases for DependencyScanService."""

    def test_service_initialization(self):
        """Test service initialization."""
        from ..src.codex_aura.analyzer.dependency_service import DependencyScanService

        service = DependencyScanService()
        assert service.scanner is not None
        assert service.neo4j_client is not None

    def test_scan_repositories_only(self):
        """Test scanning repositories without storing."""
        from ..src.codex_aura.analyzer.dependency_service import DependencyScanService

        service = DependencyScanService()

        # Create temporary repos
        with tempfile.TemporaryDirectory() as temp_dir:
            repo1_path = Path(temp_dir) / "repo1"
            repo1_path.mkdir()

            (repo1_path / "main.py").write_text('requests.get("http://api:8080")')

            graph = service.scan_repositories([repo1_path])

            assert len(graph.nodes) == 1
            assert graph.nodes[0].name == "repo1"
            assert graph.nodes[0].type == "service"