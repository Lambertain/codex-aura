"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";

interface HotspotData {
  file_path: string;
  commit_count: number;
  author_count: number;
  last_modified: string;
  lines_changed: number;
}

export function HotspotMap() {
  const { id: repoId } = useParams();

  const { data: hotspots, isLoading } = useQuery({
    queryKey: ["hotspots", repoId],
    queryFn: () => apiClient<HotspotData[]>(`/api/v1/repos/${repoId}/hotspots`),
    enabled: !!repoId,
  });

  if (isLoading) {
    return <div>Loading hotspot data...</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Code Hotspots</CardTitle>
        <p className="text-sm text-muted-foreground">
          Files with highest change frequency
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {hotspots?.slice(0, 10).map((hotspot, index) => (
            <div
              key={hotspot.file_path}
              className="flex items-center justify-between p-3 border rounded"
            >
              <div className="flex-1">
                <div className="font-medium text-sm">{hotspot.file_path}</div>
                <div className="text-xs text-muted-foreground">
                  {hotspot.commit_count} commits, {hotspot.author_count} authors
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={index < 3 ? "destructive" : "secondary"}>
                  {hotspot.lines_changed} lines
                </Badge>
                <div
                  className="w-4 h-4 rounded"
                  style={{
                    backgroundColor: `hsl(${120 - (index * 30)}, 70%, 50%)`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}