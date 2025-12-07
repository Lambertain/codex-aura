"use client";

import { useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Network,
  Filter,
  Eye,
  EyeOff,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Settings
} from "lucide-react";
import { GraphVisualization } from "@/components/graph/GraphVisualization";
import { NodeDetailsPanel } from "@/components/graph/NodeDetailsPanel";
import { GraphNode } from "@/types";
import { useGraph } from "@/hooks/useGraph";

export default function GraphPage() {
  const { id: repoId } = useParams();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [nodeFilters, setNodeFilters] = useState({
    file: true,
    class: true,
    function: true,
  });
  const [edgeFilters, setEdgeFilters] = useState({
    IMPORTS: true,
    CALLS: true,
    EXTENDS: true,
  });
  const [showDetailsPanel, setShowDetailsPanel] = useState(true);

  const { data: graphData } = useGraph(repoId as string);

  // Calculate filtered stats
  const filteredNodes = graphData?.nodes.filter(node => nodeFilters[node.type]) || [];
  const filteredEdges = graphData?.edges.filter(edge => edgeFilters[edge.type]) || [];
  const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
  const finalEdges = filteredEdges.filter(edge =>
    visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
  );

  const handleNodeSelect = useCallback((node: GraphNode | null) => {
    setSelectedNode(node);
  }, []);

  const toggleNodeFilter = (type: keyof typeof nodeFilters) => {
    setNodeFilters(prev => ({
      ...prev,
      [type]: !prev[type]
    }));
  };

  const toggleEdgeFilter = (type: keyof typeof edgeFilters) => {
    setEdgeFilters(prev => ({
      ...prev,
      [type]: !prev[type]
    }));
  };

  const resetFilters = () => {
    setNodeFilters({ file: true, class: true, function: true });
    setEdgeFilters({ IMPORTS: true, CALLS: true, EXTENDS: true });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Network className="w-8 h-8" />
            Code Graph Visualization
          </h1>
          <p className="text-muted-foreground">Interactive visualization of your codebase relationships</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowDetailsPanel(!showDetailsPanel)}
          >
            {showDetailsPanel ? <EyeOff className="w-4 h-4 mr-2" /> : <Eye className="w-4 h-4 mr-2" />}
            {showDetailsPanel ? 'Hide' : 'Show'} Details
          </Button>
        </div>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Graph Controls
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Node Filters */}
          <div>
            <label className="text-sm font-medium mb-2 block">Node Types</label>
            <div className="flex gap-2">
              {Object.entries(nodeFilters).map(([type, enabled]) => (
                <Button
                  key={type}
                  variant={enabled ? "default" : "outline"}
                  size="sm"
                  onClick={() => toggleNodeFilter(type as keyof typeof nodeFilters)}
                  className="capitalize"
                >
                  {type}
                </Button>
              ))}
            </div>
          </div>

          {/* Edge Filters */}
          <div>
            <label className="text-sm font-medium mb-2 block">Relationship Types</label>
            <div className="flex gap-2">
              {Object.entries(edgeFilters).map(([type, enabled]) => (
                <Button
                  key={type}
                  variant={enabled ? "default" : "outline"}
                  size="sm"
                  onClick={() => toggleEdgeFilter(type as keyof typeof edgeFilters)}
                  className="capitalize"
                >
                  {type.toLowerCase()}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={resetFilters}>
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Graph Container */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Graph Visualization */}
        <div className={`${showDetailsPanel ? 'lg:col-span-3' : 'lg:col-span-4'} relative`}>
          <Card className="h-[600px]">
            <CardContent className="p-0 h-full">
              <GraphVisualization
                repoId={repoId as string}
                onNodeSelect={handleNodeSelect}
                selectedNode={selectedNode}
                nodeFilters={nodeFilters}
                edgeFilters={edgeFilters}
              />
            </CardContent>
          </Card>
        </div>

        {/* Node Details Panel */}
        {showDetailsPanel && (
          <div className="lg:col-span-1">
            <NodeDetailsPanel
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
            />
          </div>
        )}
      </div>

      {/* Stats */}
      <Card>
        <CardHeader>
          <CardTitle>Graph Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {filteredNodes.length > 1000 ? '1000+' : filteredNodes.length}
              </div>
              <div className="text-sm text-muted-foreground">
                {filteredNodes.length > 1000 ? 'Displayed Nodes' : 'Total Nodes'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {finalEdges.length > 1000 ? '1000+' : finalEdges.length}
              </div>
              <div className="text-sm text-muted-foreground">
                {finalEdges.length > 1000 ? 'Displayed Edges' : 'Total Edges'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {nodeFilters.file ? filteredNodes.filter(n => n.type === 'file').length : 0}
              </div>
              <div className="text-sm text-muted-foreground">Files</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {nodeFilters.function ? filteredNodes.filter(n => n.type === 'function').length : 0}
              </div>
              <div className="text-sm text-muted-foreground">Functions</div>
            </div>
          </div>
          {filteredNodes.length > 1000 && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
              <p className="text-sm text-yellow-800">
                ⚠️ Large graph detected. Showing first 1000 nodes for optimal performance.
                Use filters to focus on specific node types.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}