"""Edge recalculation for incremental graph updates."""

import ast
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from ..models.node import Node
from ..models.edge import EdgeType
from ..storage.storage_abstraction import GraphStorage

if TYPE_CHECKING:
    from .incremental import Reference


@dataclass
class EdgeRecalcResult:
    """Result of edge recalculation operation."""
    edges_added: int
    edges_removed: int
    edges_updated: int


@dataclass
class Reference:
    """Reference from one node to another."""
    target_fqn: str
    type: EdgeType
    line: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class EdgeRecalculator:
    """Recalculate edges affected by node changes."""

    def __init__(self, track_external: bool = True):
        self.track_external = track_external

    async def recalculate(
        self,
        graph: GraphStorage,
        updated_nodes: list[Node],
        deleted_nodes: list[Node]
    ) -> EdgeRecalcResult:
        """
        Recalculate edges for changed nodes.

        Strategy:
        1. Remove all edges FROM deleted nodes
        2. Remove all edges TO deleted nodes
        3. Re-analyze edges FROM updated nodes
        4. Keep edges TO updated nodes (they're still valid targets)
        """
        result = EdgeRecalcResult(
            edges_added=0,
            edges_removed=0,
            edges_updated=0
        )

        deleted_fqns = {n.fqn for n in deleted_nodes}
        updated_fqns = {n.fqn for n in updated_nodes}

        async with graph.transaction("default") as txn:
            # Step 1: Remove edges from/to deleted nodes
            for fqn in deleted_fqns:
                removed = await txn.delete_edges_for_node(fqn)
                result.edges_removed += removed

            # Step 2: Remove outgoing edges from updated nodes
            # (incoming edges are still valid - other nodes still reference us)
            for fqn in updated_fqns:
                removed = await txn.delete_outgoing_edges(fqn)
                result.edges_removed += removed

            # Step 3: Re-analyze edges from updated nodes
            for node in updated_nodes:
                references = await self._analyze_references(node)

                for ref in references:
                    # Check if target exists in graph
                    target_exists = await txn.node_exists(ref.target_fqn)

                    if target_exists:
                        await txn.create_edge(
                            source=node.fqn,
                            target=ref.target_fqn,
                            edge_type=ref.type,
                            metadata=ref.metadata
                        )
                        result.edges_added += 1
                    else:
                        # External reference - create placeholder or skip
                        if self.track_external:
                            await txn.create_external_ref(node.fqn, ref)

        return result

    async def _analyze_references(self, node: Node) -> list[Reference]:
        """Analyze code to find references to other nodes."""
        references = []

        tree = ast.parse(node.content)

        for child in ast.walk(tree):
            # Import statements
            if isinstance(child, ast.Import):
                for alias in child.names:
                    references.append(Reference(
                        target_fqn=alias.name,
                        type=EdgeType.IMPORTS,
                        line=child.lineno
                    ))

            elif isinstance(child, ast.ImportFrom):
                module = child.module or ""
                for alias in child.names:
                    references.append(Reference(
                        target_fqn=f"{module}.{alias.name}",
                        type=EdgeType.IMPORTS,
                        line=child.lineno
                    ))

            # Function calls
            elif isinstance(child, ast.Call):
                call_target = self._resolve_call_target(child)
                if call_target:
                    references.append(Reference(
                        target_fqn=call_target,
                        type=EdgeType.CALLS,
                        line=child.lineno
                    ))

            # Class inheritance
            elif isinstance(child, ast.ClassDef):
                for base in child.bases:
                    base_name = self._resolve_base_class(base)
                    if base_name:
                        references.append(Reference(
                            target_fqn=base_name,
                            type=EdgeType.EXTENDS,
                            line=child.lineno
                        ))

        return references

    def _resolve_call_target(self, call: ast.Call) -> Optional[str]:
        """Resolve the target of a function call."""
        if isinstance(call.func, ast.Name):
            return call.func.id
        elif isinstance(call.func, ast.Attribute):
            # Handle method calls like obj.method()
            if isinstance(call.func.value, ast.Name):
                return f"{call.func.value.id}.{call.func.attr}"
        return None

    def _resolve_base_class(self, base: ast.expr) -> Optional[str]:
        """Resolve base class name from inheritance."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            # Handle qualified names like module.Class
            if isinstance(base.value, ast.Name):
                return f"{base.value.id}.{base.attr}"
        return None