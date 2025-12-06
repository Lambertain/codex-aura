"""ASCII tree visualization for dependency graphs."""

from typing import Dict, List, Set, Optional
from ..models.graph import Graph
from ..models.node import Node
from ..models.edge import Edge, EdgeType


def render_tree(
    graph: Graph,
    root_id: Optional[str] = None,
    max_depth: int = 3,
    edge_types: Optional[List[EdgeType]] = None,
    direction: str = "outgoing"
) -> str:
    """Render dependency tree as ASCII art.

    Args:
        graph: The dependency graph
        root_id: Starting node ID (defaults to first file node)
        max_depth: Maximum depth to traverse
        edge_types: Filter by edge types (default: all)
        direction: "outgoing" or "incoming"

    Returns:
        ASCII tree string

    Example output:
        src/main.py
        ├── imports: src/utils.py
        │   └── imports: src/config.py
        ├── imports: src/services/user.py
        │   ├── imports: src/utils.py
        │   └── imports: src/models/user.py
    """
    # Build adjacency map
    adj_map: Dict[str, List[tuple]] = {}  # node_id -> [(target_id, edge_type)]

    for edge in graph.edges:
        if edge_types and edge.type not in edge_types:
            continue

        if direction == "outgoing":
            source, target = edge.source, edge.target
        else:
            source, target = edge.target, edge.source

        if source not in adj_map:
            adj_map[source] = []
        adj_map[source].append((target, edge.type))

    # Find root node
    if root_id is None:
        file_nodes = [n for n in graph.nodes if n.type == "file"]
        if not file_nodes:
            return "No file nodes found in graph"
        root_id = file_nodes[0].id

    # Get node name map
    node_names: Dict[str, str] = {n.id: n.name for n in graph.nodes}

    # Render tree
    lines = []
    visited: Set[str] = set()

    def _render_node(node_id: str, prefix: str, is_last: bool, depth: int, edge_label: str = ""):
        if depth > max_depth:
            return
        if node_id in visited:
            # Show circular reference
            name = node_names.get(node_id, node_id)
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}{edge_label}{name} (circular)")
            return

        visited.add(node_id)
        name = node_names.get(node_id, node_id)

        if depth == 0:
            lines.append(name)
        else:
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{edge_label}{name}")

        # Get children
        children = adj_map.get(node_id, [])
        if not children:
            return

        # Sort children for consistent output
        children = sorted(children, key=lambda x: x[0])

        for i, (child_id, edge_type) in enumerate(children):
            is_last_child = (i == len(children) - 1)
            new_prefix = prefix + ("    " if is_last else "│   ")
            edge_str = f"{edge_type.value.lower()}: " if depth > 0 or len(children) > 0 else ""
            _render_node(child_id, new_prefix if depth > 0 else "", is_last_child, depth + 1, edge_str)

    _render_node(root_id, "", True, 0)

    return "\n".join(lines)


def render_summary_tree(graph: Graph, max_files: int = 10) -> str:
    """Render a summary tree showing top-level file dependencies.

    Args:
        graph: The dependency graph
        max_files: Maximum number of files to show

    Returns:
        ASCII summary tree
    """
    # Get file nodes sorted by connection count
    file_nodes = [n for n in graph.nodes if n.type == "file"]

    # Count connections per file
    connection_counts: Dict[str, int] = {}
    for node in file_nodes:
        incoming = sum(1 for e in graph.edges if e.target == node.id)
        outgoing = sum(1 for e in graph.edges if e.source == node.id)
        connection_counts[node.id] = incoming + outgoing

    # Sort by connections (descending)
    sorted_files = sorted(file_nodes, key=lambda n: connection_counts[n.id], reverse=True)

    lines = [f"📊 {graph.repository.name} - Dependency Summary"]
    lines.append(f"   Total: {len(file_nodes)} files, {len(graph.edges)} edges")
    lines.append("")
    lines.append("Top connected files:")

    for i, node in enumerate(sorted_files[:max_files]):
        incoming = sum(1 for e in graph.edges if e.target == node.id)
        outgoing = sum(1 for e in graph.edges if e.source == node.id)
        is_last = (i == min(len(sorted_files), max_files) - 1)
        connector = "└── " if is_last else "├── "
        lines.append(f"   {connector}{node.name} ({incoming}↓ {outgoing}↑)")

    if len(sorted_files) > max_files:
        lines.append(f"   ... and {len(sorted_files) - max_files} more files")

    return "\n".join(lines)


def render_impact_tree(
    graph: Graph,
    target_id: str,
    max_depth: int = 2
) -> str:
    """Render impact analysis tree (what depends on this node).

    Args:
        graph: The dependency graph
        target_id: Node to analyze impact for
        max_depth: Maximum depth to traverse

    Returns:
        ASCII impact tree
    """
    # Build reverse adjacency map (incoming edges)
    reverse_adj: Dict[str, List[tuple]] = {}

    for edge in graph.edges:
        if edge.target not in reverse_adj:
            reverse_adj[edge.target] = []
        reverse_adj[edge.target].append((edge.source, edge.type))

    # Get node info
    node_names: Dict[str, str] = {n.id: n.name for n in graph.nodes}
    target_name = node_names.get(target_id, target_id)

    lines = [f"🎯 Impact Analysis: {target_name}"]
    lines.append("")

    dependents = reverse_adj.get(target_id, [])
    if not dependents:
        lines.append("   No dependents found (this is a leaf node)")
        return "\n".join(lines)

    lines.append(f"   {len(dependents)} direct dependents:")

    visited: Set[str] = {target_id}

    def _render_dependent(node_id: str, prefix: str, is_last: bool, depth: int):
        if depth > max_depth or node_id in visited:
            return
        visited.add(node_id)

        name = node_names.get(node_id, node_id)
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{name}")

        # Get dependents of this node
        deps = reverse_adj.get(node_id, [])
        deps = sorted(deps, key=lambda x: x[0])

        for i, (dep_id, _) in enumerate(deps):
            is_last_dep = (i == len(deps) - 1)
            new_prefix = prefix + ("    " if is_last else "│   ")
            _render_dependent(dep_id, new_prefix, is_last_dep, depth + 1)

    dependents = sorted(dependents, key=lambda x: x[0])
    for i, (dep_id, edge_type) in enumerate(dependents):
        is_last = (i == len(dependents) - 1)
        _render_dependent(dep_id, "   ", is_last, 1)

    return "\n".join(lines)
