"""Semantic Ranking Engine for context selection.

Combines semantic similarity, graph dependencies, and criticality
to rank nodes for optimal context selection.
"""

import math
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

from ..models.node import Node, RankedNode
from ..search.embeddings import SearchResult
from ..token_budget import TokenCounter


@dataclass
class RankedContextNode:
    """Ranked node with detailed scoring information."""

    node: Node
    semantic_score: float
    graph_score: float
    combined_score: float
    tokens: int

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "node": self.node.model_dump(),
            "semantic_score": round(self.semantic_score, 3),
            "graph_score": round(self.graph_score, 3),
            "combined_score": round(self.combined_score, 3),
            "tokens": self.tokens
        }


class SemanticRankingEngine:
    """
    Engine for ranking nodes based on multiple criteria.

    Combines semantic similarity, graph proximity, criticality,
    and token efficiency for optimal context selection.
    """

    # Criticality weights by node type and name patterns
    CRITICALITY_WEIGHTS = {
        "file": {
            "patterns": [
                ("__init__.py", 0.9),
                ("models.py", 0.8),
                ("views.py", 0.8),
                ("controllers", 0.8),
                ("services", 0.7),
                ("utils", 0.6),
                ("config", 0.7),
                ("settings", 0.7),
                ("constants", 0.6),
                ("exceptions", 0.6),
                ("middleware", 0.7),
                ("serializers", 0.7),
                ("validators", 0.7),
                ("permissions", 0.8),
                ("auth", 0.9),
                ("security", 0.9),
                ("api", 0.8),
                ("tests", 0.3),  # Lower priority for tests
                ("migrations", 0.4),
            ],
            "default": 0.5
        },
        "class": {
            "patterns": [
                ("Controller", 0.9),
                ("Service", 0.8),
                ("Model", 0.8),
                ("View", 0.7),
                ("Serializer", 0.7),
                ("Validator", 0.7),
                ("Manager", 0.7),
                ("Exception", 0.6),
                ("Test", 0.2),
            ],
            "default": 0.5
        },
        "function": {
            "patterns": [
                ("__init__", 0.8),
                ("save", 0.7),
                ("create", 0.7),
                ("update", 0.7),
                ("delete", 0.7),
                ("get", 0.6),
                ("post", 0.6),
                ("put", 0.6),
                ("patch", 0.6),
                ("validate", 0.7),
                ("authenticate", 0.9),
                ("authorize", 0.9),
                ("process", 0.6),
                ("handle", 0.6),
                ("setup", 0.6),
                ("teardown", 0.5),
                ("test_", 0.2),
            ],
            "default": 0.4
        }
    }

    def __init__(self, token_counter: TokenCounter):
        self.token_counter = token_counter

    def rank_context(
        self,
        query: str,
        sem_results: List[SearchResult],
        graph_results: List[Node],
        focal_nodes: List[str] = None,
        model: str = "gpt-4"
    ) -> List[RankedContextNode]:
        """
        Rank nodes for context selection.

        Args:
            query: The task/query string
            sem_results: Semantic search results
            graph_results: Graph traversal results
            focal_nodes: Entry point node IDs (optional)
            model: Target LLM model for token counting

        Returns:
            List of ranked context nodes with detailed scores
        """
        # Create lookup maps
        semantic_scores = self._extract_semantic_scores(sem_results)
        graph_distances = self._calculate_graph_distances(graph_results, focal_nodes or [])
        file_frequencies = self._calculate_file_frequencies(graph_results)

        ranked_nodes = []

        for node in graph_results:
            # Calculate individual scores
            semantic_score = self._calculate_semantic_score(node, semantic_scores)
            graph_score = self._calculate_graph_score(node, graph_distances, focal_nodes or [])
            criticality_score = self._calculate_criticality_score(node)
            frequency_score = self._calculate_frequency_score(node, file_frequencies)

            # Token efficiency score (inverse of token cost, normalized)
            token_count = self.token_counter.count_node(node, model)
            token_efficiency = self._calculate_token_efficiency(token_count)

            # Combine scores with weights
            combined_score = self._combine_scores(
                semantic_score=semantic_score,
                graph_score=graph_score,
                criticality_score=criticality_score,
                frequency_score=frequency_score,
                token_efficiency=token_efficiency
            )

            ranked_node = RankedContextNode(
                node=node,
                semantic_score=semantic_score,
                graph_score=graph_score,
                combined_score=combined_score,
                tokens=token_count
            )

            ranked_nodes.append(ranked_node)

        # Sort by combined score descending
        ranked_nodes.sort(key=lambda x: x.combined_score, reverse=True)

        return ranked_nodes

    def _extract_semantic_scores(self, sem_results: List[SearchResult]) -> Dict[str, float]:
        """Extract semantic similarity scores from search results."""
        scores = {}

        for result in sem_results:
            # Create FQN from chunk
            if result.chunk.type == "file":
                fqn = result.chunk.file_path
            else:
                fqn = f"{result.chunk.file_path}::{result.chunk.name}"

            scores[fqn] = result.score

        return scores

    def _calculate_graph_distances(
        self,
        graph_results: List[Node],
        focal_nodes: List[str]
    ) -> Dict[str, int]:
        """Calculate minimum distance from any focal node."""
        if not focal_nodes:
            # If no focal nodes, all nodes get distance 0
            return {node.id: 0 for node in graph_results}

        distances = {}

        # Build adjacency list from graph results
        # This is simplified - in practice you'd use the full graph
        adjacency = defaultdict(list)

        # For now, assume all nodes are connected (simplified)
        # In real implementation, this would use actual graph edges

        for node in graph_results:
            if node.id in focal_nodes:
                distances[node.id] = 0
            else:
                # Calculate minimum distance (simplified BFS)
                min_distance = float('inf')
                for focal in focal_nodes:
                    # Simplified distance calculation
                    # In practice, this would be proper graph traversal
                    if focal == node.id:
                        min_distance = 0
                    else:
                        # Estimate distance based on path similarity
                        distance = self._estimate_distance(focal, node.id)
                        min_distance = min(min_distance, distance)

                distances[node.id] = min_distance if min_distance != float('inf') else 10

        return distances

    def _estimate_distance(self, focal_id: str, node_id: str) -> int:
        """Estimate distance between nodes (simplified)."""
        # Simple heuristic: same file = distance 1, same directory = 2, etc.
        if focal_id == node_id:
            return 0

        # Extract file paths
        focal_path = focal_id.split("::")[0] if "::" in focal_id else focal_id
        node_path = node_id.split("::")[0] if "::" in node_id else node_id

        if focal_path == node_path:
            return 1  # Same file

        # Check directory similarity
        focal_parts = focal_path.split("/")
        node_parts = node_path.split("/")

        # Find common prefix
        common = 0
        for i, (f, n) in enumerate(zip(focal_parts, node_parts)):
            if f == n:
                common = i + 1
            else:
                break

        # Distance based on directory depth difference
        depth_diff = abs(len(focal_parts) - len(node_parts))
        distance = max(2, 5 - common + depth_diff)

        return min(distance, 10)  # Cap at 10

    def _calculate_file_frequencies(self, graph_results: List[Node]) -> Dict[str, int]:
        """Calculate how often each file appears in results."""
        frequencies = defaultdict(int)

        for node in graph_results:
            frequencies[node.path] += 1

        return dict(frequencies)

    def _calculate_semantic_score(self, node: Node, semantic_scores: Dict[str, float]) -> float:
        """Calculate semantic similarity score."""
        fqn = node.fqn
        return semantic_scores.get(fqn, 0.0)

    def _calculate_graph_score(
        self,
        node: Node,
        distances: Dict[str, int],
        focal_nodes: List[str]
    ) -> float:
        """Calculate graph proximity score."""
        if not focal_nodes:
            return 0.5  # Neutral score

        distance = distances.get(node.id, 10)

        # Convert distance to score: closer = higher score
        # Score = 1 / (1 + distance)
        score = 1.0 / (1.0 + distance)

        # Boost focal nodes
        if node.id in focal_nodes:
            score = 1.0

        return score

    def _calculate_criticality_score(self, node: Node) -> float:
        """Calculate criticality score based on node type and name."""
        type_weights = self.CRITICALITY_WEIGHTS.get(node.type, {"patterns": [], "default": 0.5})

        # Check name patterns
        name_lower = node.name.lower()
        for pattern, weight in type_weights["patterns"]:
            if pattern.lower() in name_lower:
                return weight

        return type_weights["default"]

    def _calculate_frequency_score(self, node: Node, file_frequencies: Dict[str, int]) -> float:
        """Calculate frequency score (how often file appears)."""
        freq = file_frequencies.get(node.path, 1)
        total_files = len(file_frequencies)

        # Normalize frequency score
        if total_files == 0:
            return 0.5

        # Higher frequency = slightly higher score (diminishing returns)
        score = math.log(freq + 1) / math.log(total_files + 1)
        return min(score, 1.0)

    def _calculate_token_efficiency(self, token_count: int) -> float:
        """Calculate token efficiency score (inverse of cost)."""
        if token_count <= 0:
            return 0.0

        # Efficiency = 1 / log(token_count + 1)
        # Higher tokens = lower efficiency
        efficiency = 1.0 / math.log(token_count + 1)

        # Normalize to [0, 1]
        return min(efficiency * 2, 1.0)  # Scale factor for balance

    def _combine_scores(
        self,
        semantic_score: float,
        graph_score: float,
        criticality_score: float,
        frequency_score: float,
        token_efficiency: float
    ) -> float:
        """Combine individual scores into final ranking score."""
        # Weights for different factors
        weights = {
            "semantic": 0.4,      # Most important
            "graph": 0.3,         # Important for context coherence
            "criticality": 0.15,  # Important for key components
            "frequency": 0.1,     # Minor boost for frequently referenced
            "token_efficiency": 0.05  # Minor penalty for large nodes
        }

        combined = (
            weights["semantic"] * semantic_score +
            weights["graph"] * graph_score +
            weights["criticality"] * criticality_score +
            weights["frequency"] * frequency_score +
            weights["token_efficiency"] * token_efficiency
        )

        return min(combined, 1.0)  # Cap at 1.0


# Convenience function for API usage
def rank_context(
    query: str,
    sem_results: List[SearchResult],
    graph_results: List[Node],
    focal_nodes: List[str] = None,
    model: str = "gpt-4"
) -> List[RankedContextNode]:
    """
    Convenience function to rank context nodes.

    Args:
        query: Task/query string
        sem_results: Semantic search results
        graph_results: Graph nodes
        focal_nodes: Entry point node IDs
        model: Target model for token counting

    Returns:
        Ranked context nodes
    """
    token_counter = TokenCounter()
    engine = SemanticRankingEngine(token_counter)

    return engine.rank_context(query, sem_results, graph_results, focal_nodes, model)