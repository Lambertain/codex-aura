"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { useGraph } from "@/hooks/useGraph";
import { GraphNode, GraphEdge } from "@/types";

interface GraphVisualizationProps {
  repoId: string;
  onNodeSelect: (node: GraphNode | null) => void;
  selectedNode: GraphNode | null;
  nodeFilters?: { file: boolean; class: boolean; function: boolean };
  edgeFilters?: { IMPORTS: boolean; CALLS: boolean; EXTENDS: boolean };
}

export function GraphVisualization({
  repoId,
  onNodeSelect,
  selectedNode,
  nodeFilters = { file: true, class: true, function: true },
  edgeFilters = { IMPORTS: true, CALLS: true, EXTENDS: true }
}: GraphVisualizationProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: graphData, isLoading } = useGraph(repoId);

  useEffect(() => {
    if (!graphData || !svgRef.current || !containerRef.current) return;

    const svg = d3.select(svgRef.current);
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Clear previous
    svg.selectAll("*").remove();

    // Filter nodes and edges based on filters
    const filteredNodes = graphData.nodes.filter(node => nodeFilters[node.type]);
    const filteredEdges = graphData.edges.filter(edge => edgeFilters[edge.type]);

    // Performance optimization: limit nodes for large graphs
    const MAX_NODES = 1000; // Limit for smooth performance
    const shouldLimit = filteredNodes.length > MAX_NODES;

    let displayNodes = filteredNodes;
    let displayEdges = filteredEdges;

    if (shouldLimit) {
      // For large graphs, show a subset and warn user
      displayNodes = filteredNodes.slice(0, MAX_NODES);
      const visibleNodeIds = new Set(displayNodes.map(n => n.id));
      displayEdges = filteredEdges.filter(edge =>
        visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
      );
    } else {
      // Only include edges where both source and target nodes are visible
      const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
      displayEdges = filteredEdges.filter(edge =>
        visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
      );
    }

    // Focus on node function
    const focusOnNode = (targetNode: GraphNode) => {
      // Find connected nodes
      const connectedNodeIds = new Set<string>();

      displayEdges.forEach(edge => {
        const sourceId = typeof edge.source === 'string' ? edge.source : (edge.source as any).id;
        const targetId = typeof edge.target === 'string' ? edge.target : (edge.target as any).id;

        if (sourceId === targetNode.id) {
          connectedNodeIds.add(targetId);
        } else if (targetId === targetNode.id) {
          connectedNodeIds.add(sourceId);
        }
      });

      // Update visual highlighting
      const svg = d3.select(svgRef.current!);
      const g = svg.select("g");

      // Dim non-connected nodes
      g.selectAll("g")
        .attr("opacity", (d: any) =>
          d.id === targetNode.id || connectedNodeIds.has(d.id) ? 1 : 0.1
        );

      // Highlight connected edges
      g.selectAll("line")
        .attr("stroke-opacity", (d: any) => {
          const sourceId = typeof d.source === 'string' ? d.source : (d.source as any).id;
          const targetId = typeof d.target === 'string' ? d.target : (d.target as any).id;
          return (sourceId === targetNode.id || targetId === targetNode.id) ? 1 : 0.1;
        })
        .attr("stroke-width", (d: any) => {
          const sourceId = typeof d.source === 'string' ? d.source : (d.source as any).id;
          const targetId = typeof d.target === 'string' ? d.target : (d.target as any).id;
          return (sourceId === targetNode.id || targetId === targetNode.id) ? 3 : 1.5;
        });
    };

    // Setup zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    const g = svg.append("g");

    // Color scale for node types
    const colorScale = d3.scaleOrdinal<string>()
      .domain(["file", "class", "function"])
      .range(["#6366f1", "#8b5cf6", "#a855f7"]);

    // Edge color scale
    const edgeColorScale = d3.scaleOrdinal<string>()
      .domain(["IMPORTS", "CALLS", "EXTENDS"])
      .range(["#94a3b8", "#22c55e", "#f59e0b"]);

    // Force simulation
    const simulation = d3.forceSimulation(displayNodes as d3.SimulationNodeDatum[])
      .force("link", d3.forceLink(displayEdges)
        .id((d: any) => d.id)
        .distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(30));

    // Draw edges
    const link = g.append("g")
      .selectAll("line")
      .data(displayEdges)
      .join("line")
      .attr("stroke", d => edgeColorScale(d.type))
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", 1.5);

    // Draw nodes
    const node = g.append("g")
      .selectAll("g")
      .data(displayNodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(d3.drag<any, GraphNode>()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    // Node circles
    node.append("circle")
      .attr("r", d => d.type === "file" ? 20 : d.type === "class" ? 15 : 10)
      .attr("fill", d => colorScale(d.type))
      .attr("stroke", "#fff")
      .attr("stroke-width", 2);

    // Node labels
    node.append("text")
      .text(d => d.name.length > 15 ? d.name.slice(0, 15) + "..." : d.name)
      .attr("x", 0)
      .attr("y", d => (d.type === "file" ? 20 : d.type === "class" ? 15 : 10) + 15)
      .attr("text-anchor", "middle")
      .attr("font-size", "10px")
      .attr("fill", "#64748b");

    // Click handler
    node.on("click", (event, d) => {
      event.stopPropagation();
      onNodeSelect(d);
    });

    // Double-click handler for focus
    node.on("dblclick", (event, d) => {
      event.stopPropagation();
      focusOnNode(d);
    });

    // Background click to deselect
    svg.on("click", () => onNodeSelect(null));

    // Highlight selected node
    node.attr("opacity", d =>
      selectedNode ? (d.id === selectedNode.id ? 1 : 0.3) : 1
    );

    // Simulation tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });

    // Drag functions
    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: any) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return () => {
      simulation.stop();
    };
  }, [graphData, selectedNode, onNodeSelect, nodeFilters, edgeFilters]);

  if (isLoading) {
    return <div className="flex items-center justify-center h-full">Loading graph...</div>;
  }

  return (
    <div ref={containerRef} className="w-full h-full">
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}