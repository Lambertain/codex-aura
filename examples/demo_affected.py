#!/usr/bin/env python3
"""Demo script to show affected files when changing a source file."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codex_aura.models.graph import load_graph


def main():
    """Main function."""
    if len(sys.argv) != 3:
        print("Usage: python examples/demo_affected.py <graph.json> <file_path>")
        print("Example: python examples/demo_affected.py graph.json src/utils.py")
        sys.exit(1)

    graph_file = Path(sys.argv[1])
    target_file = sys.argv[2]

    if not graph_file.exists():
        print(f"Error: Graph file not found: {graph_file}")
        sys.exit(1)

    try:
        graph = load_graph(graph_file)
    except Exception as e:
        print(f"Error loading graph: {e}")
        sys.exit(1)

    # Find the target file node
    target_node = None
    for node in graph.nodes:
        if node.type == "file" and node.path == target_file:
            target_node = node
            break

    if not target_node:
        print(f"Error: File not found in graph: {target_file}")
        print("Available files:")
        for node in graph.nodes:
            if node.type == "file":
                print(f"  {node.path}")
        sys.exit(1)

    print(f"🎯 Analyzing impact of changes to: {target_file}")
    print()

    # Find incoming edges (files that import this file)
    incoming_files = []
    for edge in graph.edges:
        if edge.target == target_node.id:
            # Find the source file
            for node in graph.nodes:
                if node.id == edge.source and node.type == "file":
                    incoming_files.append((node.path, edge.line))
                    break

    # Find outgoing edges (files that this file imports)
    outgoing_files = []
    for edge in graph.edges:
        if edge.source == target_node.id:
            # Find the target file
            for node in graph.nodes:
                if node.id == edge.target and node.type == "file":
                    outgoing_files.append((node.path, edge.line))
                    break

    # Remove duplicates and sort
    incoming_files = sorted(set(incoming_files))
    outgoing_files = sorted(set(outgoing_files))

    print("📥 Files that IMPORT this file (will be affected):")
    if incoming_files:
        for file_path, line in incoming_files:
            print(f"   • {file_path} (line {line})")
    else:
        print("   (none)")

    print()
    print("📤 Files that this file IMPORTS (dependencies):")
    if outgoing_files:
        for file_path, line in outgoing_files:
            print(f"   • {file_path} (line {line})")
    else:
        print("   (none)")

    total_affected = len(incoming_files) + len(outgoing_files)
    print()
    print(f"🔄 Total impact: {total_affected} files")


if __name__ == "__main__":
    main()