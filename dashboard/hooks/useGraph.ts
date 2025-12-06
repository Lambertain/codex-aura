import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { GraphNode, GraphEdge } from "@/types";

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export function useGraph(repoId: string) {
  return useQuery({
    queryKey: ["graph", repoId],
    queryFn: () => apiClient<GraphData>(`/api/v1/repos/${repoId}/graph`),
    enabled: !!repoId,
  });
}