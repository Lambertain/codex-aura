"""Graph difference calculation engine for comparing code dependency graphs."""

import hashlib
import json
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from ..models.node import Node
from ..models.edge import Edge
from ..storage.postgres_snapshots import PostgresSnapshotStorage


@dataclass
class GraphDiffResult:
    """Result of graph difference calculation."""

    added_nodes: List[Dict]
    removed_nodes: List[Dict]
    changed_nodes: List[Dict]
    added_edges: List[Dict]
    removed_edges: List[Dict]


class GraphDiffEngine:
    """Engine for calculating differences between two code dependency graphs."""

    def __init__(self, snapshot_storage: Optional[PostgresSnapshotStorage] = None):
        """
        Initialize the graph diff engine.

        Args:
            snapshot_storage: Storage for graph snapshots, creates default if None
        """
        self.snapshot_storage = snapshot_storage or PostgresSnapshotStorage()

    async def calculate(self, repo_id: str, sha_old: str, sha_new: str) -> GraphDiffResult:
        """
        Calculate the difference between two graph snapshots.

        Args:
            repo_id: Repository identifier
            sha_old: SHA of the old graph
            sha_new: SHA of the new graph

        Returns:
            GraphDiffResult containing the differences

        Raises:
            ValueError: If either snapshot is not found
        """
        # Get snapshots
        old_snapshot = await self.snapshot_storage.get_snapshot_for_sha(repo_id, sha_old)
        new_snapshot = await self.snapshot_storage.get_snapshot_for_sha(repo_id, sha_new)

        if not old_snapshot:
            raise ValueError(f"Snapshot not found for SHA {sha_old}")
        if not new_snapshot:
            raise ValueError(f"Snapshot not found for SHA {sha_new}")

        # Get nodes and edges
        old_nodes = await self.snapshot_storage.get_snapshot_nodes(old_snapshot.snapshot_id)
        new_nodes = await self.snapshot_storage.get_snapshot_nodes(new_snapshot.snapshot_id)
        old_edges = await self.snapshot_storage.get_snapshot_edges(old_snapshot.snapshot_id)
        new_edges = await self.snapshot_storage.get_snapshot_edges(new_snapshot.snapshot_id)

        # Calculate differences
        added_nodes, removed_nodes, changed_nodes = self._calculate_node_differences(old_nodes, new_nodes)
        added_edges, removed_edges = self._calculate_edge_differences(old_edges, new_edges)

        return GraphDiffResult(
            added_nodes=added_nodes,
            removed_nodes=removed_nodes,
            changed_nodes=changed_nodes,
            added_edges=added_edges,
            removed_edges=removed_edges
        )

    def _calculate_node_differences(
        self,
        old_nodes: List[Dict],
        new_nodes: List[Dict]
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Calculate node differences between two node sets.

        Args:
            old_nodes: Nodes from old graph
            new_nodes: Nodes from new graph

        Returns:
            Tuple of (added_nodes, removed_nodes, changed_nodes)
        """
        # Create lookup dictionaries by node_id
        old_nodes_by_id = {node['node_id']: node for node in old_nodes}
        new_nodes_by_id = {node['node_id']: node for node in new_nodes}

        # Find added and removed nodes
        old_ids = set(old_nodes_by_id.keys())
        new_ids = set(new_nodes_by_id.keys())

        added_node_ids = new_ids - old_ids
        removed_node_ids = old_ids - new_ids
        common_node_ids = old_ids & new_ids

        # Added nodes
        added_nodes = [new_nodes_by_id[node_id] for node_id in added_node_ids]

        # Removed nodes
        removed_nodes = [old_nodes_by_id[node_id] for node_id in removed_node_ids]

        # Changed nodes (same ID but different properties)
        changed_nodes = []
        for node_id in common_node_ids:
            old_node = old_nodes_by_id[node_id]
            new_node = new_nodes_by_id[node_id]

            if self._nodes_differ(old_node, new_node):
                changed_nodes.append({
                    'node_id': node_id,
                    'old_properties': old_node,
                    'new_properties': new_node
                })

        return added_nodes, removed_nodes, changed_nodes

    def _calculate_edge_differences(
        self,
        old_edges: List[Dict],
        new_edges: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Calculate edge differences between two edge sets.

        Args:
            old_edges: Edges from old graph
            new_edges: Edges from new graph

        Returns:
            Tuple of (added_edges, removed_edges)
        """
        # Create sets of edge tuples for comparison
        # Edge tuple: (source_id, target_id, edge_type)
        old_edge_tuples = {(e['source_id'], e['target_id'], e['edge_type']) for e in old_edges}
        new_edge_tuples = {(e['source_id'], e['target_id'], e['edge_type']) for e in new_edges}

        # Find added and removed edges
        added_edge_tuples = new_edge_tuples - old_edge_tuples
        removed_edge_tuples = old_edge_tuples - new_edge_tuples

        # Convert back to dict format
        added_edges = []
        for source_id, target_id, edge_type in added_edge_tuples:
            # Find the edge dict from new_edges
            edge_dict = next(
                (e for e in new_edges
                 if e['source_id'] == source_id and e['target_id'] == target_id and e['edge_type'] == edge_type),
                {'source_id': source_id, 'target_id': target_id, 'edge_type': edge_type, 'line_number': None}
            )
            added_edges.append(edge_dict)

        removed_edges = []
        for source_id, target_id, edge_type in removed_edge_tuples:
            # Find the edge dict from old_edges
            edge_dict = next(
                (e for e in old_edges
                 if e['source_id'] == source_id and e['target_id'] == target_id and e['edge_type'] == edge_type),
                {'source_id': source_id, 'target_id': target_id, 'edge_type': edge_type, 'line_number': None}
            )
            removed_edges.append(edge_dict)

        return added_edges, removed_edges

    def _nodes_differ(self, old_node: Dict, new_node: Dict) -> bool:
        """
        Check if two nodes differ based on their properties hash.

        Args:
            old_node: Old node properties
            new_node: New node properties

        Returns:
            True if nodes differ, False otherwise
        """
        # Calculate property hashes excluding node_id (which is the key)
        old_hash = self._calculate_node_properties_hash(old_node)
        new_hash = self._calculate_node_properties_hash(new_node)

        return old_hash != new_hash

    def _calculate_node_properties_hash(self, node: Dict) -> str:
        """
        Calculate hash of node properties for comparison.

        Args:
            node: Node dictionary

        Returns:
            SHA256 hash of the properties
        """
        # Create a copy without node_id and sort keys for consistent hashing
        properties = {k: v for k, v in node.items() if k != 'node_id'}
        properties_str = json.dumps(properties, sort_keys=True, default=str)

        return hashlib.sha256(properties_str.encode()).hexdigest()