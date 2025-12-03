#!/usr/bin/env python3
"""Demo script to visualize import graph as ASCII tree."""

import sys
from pathlib import Path
from typing import Dict, List, Set

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codex_aura.models.graph import load_graph


def build_import_tree(graph, root_file: str, max_depth: int = 3) -> Dict[str, List[str]]:
    """Build import tree from root file."""
    # Find root node
    root_node = None
    for node in graph.nodes:
        if node.type == "file" and node.path == root_file:
            root_node = node
            break

    if not root_node:
        return {}

    # Build adjacency list: file -> list of files it imports
    imports = {}
    for node in graph.nodes:
        if node.type == "file":
            imports[node.path] = []

    for edge in graph.edges:
        if edge.type.value == "IMPORTS":
            # Find source and target file paths
            source_path = None
            target_path = None
            for node in graph.nodes:
                if node.id == edge.source and node.type == "file":
                    source_path = node.path
                elif node.id == edge.target and node.type == "file":
                    target_path = node.path
            if source_path and target_path:
                imports[source_path].append(target_path)

    # Build tree with depth limit
    tree = {}
    visited = set()

    def dfs(current: str, depth: int):
        if depth > max_depth or current in visited:
            return
        visited.add(current)
        tree[current] = imports.get(current, [])[:]
        for child in tree[current]:
            dfs(child, depth + 1)

    dfs(root_file, 0)
    return tree


def print_tree(tree: Dict[str, List[str]], root: str, prefix: str = ""):
    """Print ASCII tree."""
    if root not in tree:
        return

    children = tree[root]
    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        if is_last:
            branch = "└── imports: "
            next_prefix = prefix + "    "
        else:
            branch = "├── imports: "
            next_prefix = prefix + "│   "

        print(f"{prefix}{branch}{child}")
        print_tree(tree, child, next_prefix)


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python examples/demo_visualize.py <graph.json> <root_file> [--depth N]")
        print("Example: python examples/demo_visualize.py graph.json src/main.py --depth 2")
        sys.exit(1)

    graph_file = Path(sys.argv[1])
    root_file = sys.argv[2]
    max_depth = 3  # default

    # Parse --depth option
    if len(sys.argv) > 3 and sys.argv[3] == "--depth":
        try:
            max_depth = int(sys.argv[4])
        except (IndexError, ValueError):
            print("Error: --depth requires a number")
            sys.exit(1)

    if not graph_file.exists():
        print(f"Error: Graph file not found: {graph_file}")
        sys.exit(1)

    try:
        graph = load_graph(graph_file)
    except Exception as e:
        print(f"Error loading graph: {e}")
        sys.exit(1)

    tree = build_import_tree(graph, root_file, max_depth)

    if not tree:
        print(f"Error: Root file not found in graph: {root_file}")
        print("Available files:")
        for node in graph.nodes:
            if node.type == "file":
                print(f"  {node.path}")
        sys.exit(1)

    print(root_file)
    print_tree(tree, root_file)


if __name__ == "__main__":
    main()