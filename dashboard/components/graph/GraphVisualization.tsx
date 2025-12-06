"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { useGraph } from "@/hooks/useGraph";
import { GraphNode, GraphEdge } from "@/types";

interface GraphVisualizationProps {
  repoId: string;
  onNodeSelect: (node: GraphNode | null) => void;
  selectedNode: GraphNode | null;
}

export function GraphVisualization({
  repoId,
  onNodeSelect,
  selectedNode
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
    const simulation = d3.forceSimulation(graphData.nodes as d3.SimulationNodeDatum[])
      .force("link", d3.forceLink(graphData.edges)
        .id((d: any) => d.id)
        .distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(30));

    // Draw edges
    const link = g.append("g")
      .selectAll("line")
      .data(graphData.edges)
      .join("line")
      .attr("stroke", d => edgeColorScale(d.type))
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", 1.5);

    // Draw nodes
    const node = g.append("g")
      .selectAll("g")
      .data(graphData.nodes)
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
  }, [graphData, selectedNode, onNodeSelect]);

  if (isLoading) {
    return <div className="flex items-center justify-center h-full">Loading graph...</div>;
  }

  return (
    <div ref={containerRef} className="w-full h-full">
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}