"""Clustering functionality for grouping nodes by themes/modules using embeddings."""

from typing import List, Dict, Any
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from hdbscan import HDBSCAN
from .embeddings import EmbeddingService
from ..models.node import Node


class NodeCluster:
    """Represents a cluster of nodes with metadata."""

    def __init__(self, cluster_id: int, nodes: List[Node], centroid: np.ndarray = None):
        self.cluster_id = cluster_id
        self.nodes = nodes
        self.centroid = centroid
        self.label = f"Cluster {cluster_id}"

    @property
    def size(self) -> int:
        return len(self.nodes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "label": self.label,
            "size": self.size,
            "nodes": [node.id for node in self.nodes],
            "centroid": self.centroid.tolist() if self.centroid is not None else None
        }


class NodeClustering:
    """Service for clustering nodes using embeddings."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    async def get_node_embeddings(self, nodes: List[Node]) -> List[List[float]]:
        """Generate embeddings for nodes."""
        contents = []
        for node in nodes:
            # Use node content or name/path as fallback
            content = node.content or f"{node.type} {node.name} in {node.path}"
            contents.append(content)

        return await self.embedding_service.embed_batch(contents)

    def cluster_nodes_kmeans(
        self,
        nodes: List[Node],
        embeddings: List[List[float]],
        k: int = 8,
        random_state: int = 42
    ) -> List[NodeCluster]:
        """Cluster nodes using K-means algorithm."""
        if len(nodes) < k:
            k = max(1, len(nodes))

        X = np.array(embeddings)
        kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = kmeans.fit_predict(X)

        clusters = []
        for cluster_id in range(k):
            cluster_nodes = [
                node for node, label in zip(nodes, labels)
                if label == cluster_id
            ]
            if cluster_nodes:  # Only create cluster if it has nodes
                centroid = kmeans.cluster_centers_[cluster_id]
                cluster = NodeCluster(cluster_id, cluster_nodes, centroid)
                clusters.append(cluster)

        return clusters

    def cluster_nodes_hdbscan(
        self,
        nodes: List[Node],
        embeddings: List[List[float]],
        min_cluster_size: int = 5,
        min_samples: int = None
    ) -> List[NodeCluster]:
        """Cluster nodes using HDBSCAN algorithm."""
        X = np.array(embeddings)

        if min_samples is None:
            min_samples = min_cluster_size

        hdbscan = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples)
        labels = hdbscan.fit_predict(X)

        # HDBSCAN assigns -1 to noise points
        unique_labels = set(labels)
        unique_labels.discard(-1)  # Remove noise label

        clusters = []
        for cluster_id in unique_labels:
            cluster_nodes = [
                node for node, label in zip(nodes, labels)
                if label == cluster_id
            ]
            if cluster_nodes:
                # Calculate centroid for labeled clusters
                cluster_embeddings = np.array([
                    embeddings[i] for i, label in enumerate(labels)
                    if label == cluster_id
                ])
                centroid = np.mean(cluster_embeddings, axis=0)
                cluster = NodeCluster(cluster_id, cluster_nodes, centroid)
                clusters.append(cluster)

        # Handle noise points if any
        noise_nodes = [
            node for node, label in zip(nodes, labels)
            if label == -1
        ]
        if noise_nodes:
            # Create a noise cluster with id -1
            noise_cluster = NodeCluster(-1, noise_nodes)
            noise_cluster.label = "Noise/Unclustered"
            clusters.append(noise_cluster)

        return clusters

    def generate_cluster_labels(
        self,
        clusters: List[NodeCluster],
        use_ai: bool = False
    ) -> List[NodeCluster]:
        """Generate descriptive labels for clusters based on their content."""
        for cluster in clusters:
            if cluster.cluster_id == -1:
                continue  # Skip noise cluster

            # Simple heuristic-based labeling
            types = [node.type for node in cluster.nodes]
            paths = [node.path for node in cluster.nodes]
            names = [node.name for node in cluster.nodes]

            # Count most common type
            type_counts = {}
            for t in types:
                type_counts[t] = type_counts.get(t, 0) + 1
            dominant_type = max(type_counts, key=type_counts.get)

            # Extract common path prefixes
            if paths:
                common_prefix = self._find_common_prefix(paths)
                if common_prefix:
                    cluster.label = f"{dominant_type.title()}s in {common_prefix}"
                else:
                    cluster.label = f"{dominant_type.title()}s ({len(cluster.nodes)} items)"
            else:
                cluster.label = f"Mixed cluster ({len(cluster.nodes)} items)"

        return clusters

    def _find_common_prefix(self, paths: List[str]) -> str:
        """Find common directory prefix among paths."""
        if not paths:
            return ""

        # Split paths into components
        path_parts = [path.split('/') for path in paths]

        # Find minimum length
        min_len = min(len(parts) for parts in path_parts)

        common_parts = []
        for i in range(min_len):
            part = path_parts[0][i]
            if all(parts[i] == part for parts in path_parts):
                common_parts.append(part)
            else:
                break

        return '/'.join(common_parts) if common_parts else ""

    def evaluate_clustering(
        self,
        embeddings: List[List[float]],
        labels: List[int]
    ) -> Dict[str, float]:
        """Evaluate clustering quality using silhouette score."""
        if len(set(labels)) < 2:
            return {"silhouette_score": 0.0}

        X = np.array(embeddings)
        try:
            score = silhouette_score(X, labels)
            return {"silhouette_score": score}
        except:
            return {"silhouette_score": 0.0}


async def cluster_nodes(
    nodes: List[Node],
    k: int = 8,
    algorithm: str = "kmeans",
    embedding_service: EmbeddingService = None,
    **kwargs
) -> List[NodeCluster]:
    """Main clustering function.

    Args:
        nodes: List of nodes to cluster
        k: Number of clusters (for k-means)
        algorithm: "kmeans" or "hdbscan"
        embedding_service: Embedding service instance
        **kwargs: Additional parameters for clustering algorithms

    Returns:
        List of NodeCluster objects
    """
    if not nodes:
        return []

    if embedding_service is None:
        embedding_service = EmbeddingService()

    clustering = NodeClustering(embedding_service)

    # Get embeddings
    embeddings = await clustering.get_node_embeddings(nodes)

    # Cluster based on algorithm
    if algorithm.lower() == "kmeans":
        clusters = clustering.cluster_nodes_kmeans(nodes, embeddings, k=k, **kwargs)
    elif algorithm.lower() == "hdbscan":
        clusters = clustering.cluster_nodes_hdbscan(nodes, embeddings, **kwargs)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    # Generate labels
    clusters = clustering.generate_cluster_labels(clusters)

    return clusters