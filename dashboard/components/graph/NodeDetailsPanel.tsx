import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Copy, ExternalLink, GitBranch, FileCode, Users, ArrowRight, Code2, Info } from "lucide-react";
import { apiClient } from "@/lib/api";
import { GraphNode } from "@/types";

interface NodeDetailsPanelProps {
  node: GraphNode | null;
  onClose: () => void;
}

export function NodeDetailsPanel({ node, onClose }: NodeDetailsPanelProps) {
  if (!node) return null;

  const { data: nodeDetails } = useQuery({
    queryKey: ["node", node.id],
    queryFn: () => apiClient(`/api/v1/nodes/${node.id}`),
    enabled: !!node,
  });

  const copyFqn = () => {
    navigator.clipboard.writeText(node.fqn);
  };

  return (
    <Card className="w-96 max-h-[80vh] overflow-auto">
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle className="text-lg">{node.name}</CardTitle>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="secondary">{node.type}</Badge>
            <span className="text-sm text-muted-foreground">{node.file_path}</span>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          ×
        </Button>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* FQN */}
        <div>
          <label className="text-sm font-medium">Fully Qualified Name</label>
          <div className="flex items-center gap-2 mt-1">
            <code className="text-sm bg-muted px-2 py-1 rounded flex-1 truncate">
              {node.fqn}
            </code>
            <Button variant="ghost" size="icon" onClick={copyFqn}>
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Dependencies */}
        {nodeDetails?.dependencies && (
          <div>
            <label className="text-sm font-medium">
              Dependencies ({nodeDetails.dependencies.length})
            </label>
            <div className="mt-1 space-y-1">
              {nodeDetails.dependencies.slice(0, 5).map((dep: any) => (
                <div key={dep.fqn} className="text-sm flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">{dep.edge_type}</Badge>
                  <span className="truncate">{dep.name}</span>
                </div>
              ))}
              {nodeDetails.dependencies.length > 5 && (
                <span className="text-sm text-muted-foreground">
                  +{nodeDetails.dependencies.length - 5} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Code Preview */}
        {nodeDetails?.content && (
          <div>
            <label className="text-sm font-medium flex items-center gap-2">
              <Code2 className="w-4 h-4" />
              Code Preview
            </label>
            <div className="mt-1 rounded overflow-hidden max-h-64">
              <pre className="p-3 text-sm bg-muted overflow-x-auto border rounded">
                <code>{nodeDetails.content}</code>
              </pre>
            </div>
          </div>
        )}

        {/* Statistics */}
        {nodeDetails?.stats && (
          <div>
            <label className="text-sm font-medium flex items-center gap-2">
              <Info className="w-4 h-4" />
              Statistics
            </label>
            <div className="mt-1 space-y-2">
              <div className="flex justify-between text-sm">
                <span>Lines of code:</span>
                <span className="font-medium">{nodeDetails.stats.lines || 'N/A'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Complexity:</span>
                <span className="font-medium">{nodeDetails.stats.complexity || 'N/A'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Last modified:</span>
                <span className="font-medium">
                  {nodeDetails.stats.lastModified ? new Date(nodeDetails.stats.lastModified).toLocaleDateString() : 'N/A'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="flex-1">
            <ExternalLink className="w-4 h-4 mr-2" />
            View in GitHub
          </Button>
          <Button variant="outline" size="sm" className="flex-1">
            <GitBranch className="w-4 h-4 mr-2" />
            Show Dependents
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}