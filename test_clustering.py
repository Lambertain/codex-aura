#!/usr/bin/env python3
"""Simple test script for clustering functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test imports
try:
    from codex_aura.models.node import Node
    print("✓ Node import successful")
except ImportError as e:
    print(f"✗ Node import failed: {e}")
    sys.exit(1)

try:
    from codex_aura.search.embeddings import EmbeddingService
    print("✓ EmbeddingService import successful")
except ImportError as e:
    print(f"✗ EmbeddingService import failed: {e}")
    sys.exit(1)

try:
    from codex_aura.search.clustering import cluster_nodes, NodeCluster
    print("✓ Clustering imports successful")
except ImportError as e:
    print(f"✗ Clustering import failed: {e}")
    sys.exit(1)

# Test basic functionality
print("\nTesting basic clustering functionality...")

# Create test nodes
nodes = [
    Node(id="auth.py", type="file", name="auth.py", path="auth.py", content="Authentication module for user login"),
    Node(id="user.py", type="file", name="user.py", path="user.py", content="User management and profiles"),
    Node(id="order.py", type="file", name="order.py", path="order.py", content="Order processing and management"),
    Node(id="payment.py", type="file", name="payment.py", path="payment.py", content="Payment processing system"),
    Node(id="email.py", type="file", name="email.py", path="email.py", content="Email notification service"),
    Node(id="db.py", type="file", name="db.py", path="db.py", content="Database connection and utilities"),
]

print(f"Created {len(nodes)} test nodes")

# Test cluster creation
try:
    cluster = NodeCluster(0, nodes[:2])
    print(f"✓ NodeCluster creation successful: {cluster.label}, size: {cluster.size}")
except Exception as e:
    print(f"✗ NodeCluster creation failed: {e}")
    sys.exit(1)

# Test model validation
try:
    from codex_aura.api.server import ClusterRequest, ClusterResponse
    print("✓ API models import successful")

    # Test request validation
    request = ClusterRequest(repo_id="test_repo", k=3, algorithm="kmeans")
    print(f"✓ ClusterRequest validation successful: {request.algorithm}, k={request.k}")

    # Test response creation
    response = ClusterResponse(
        clusters=[{"cluster_id": 0, "label": "Test", "size": 2, "nodes": ["a", "b"]}],
        total_nodes=2,
        algorithm="kmeans",
        k=3
    )
    print(f"✓ ClusterResponse creation successful: {len(response.clusters)} clusters")

except Exception as e:
    print(f"✗ API models test failed: {e}")
    sys.exit(1)

print("\n✓ All basic tests passed!")
print("Note: Full clustering test requires OpenAI API key and may incur costs.")