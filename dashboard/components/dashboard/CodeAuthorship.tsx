"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";

interface AuthorData {
  author: string;
  email: string;
  commits: number;
  lines_added: number;
  lines_deleted: number;
  files_modified: number;
  last_commit: string;
}

export function CodeAuthorship() {
  const { id: repoId } = useParams();

  const { data: authors, isLoading } = useQuery({
    queryKey: ["authorship", repoId],
    queryFn: () => apiClient<AuthorData[]>(`/api/v1/repos/${repoId}/authorship`),
    enabled: !!repoId,
  });

  if (isLoading) {
    return <div>Loading authorship data...</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Code Authorship</CardTitle>
        <p className="text-sm text-muted-foreground">
          Contributors and their impact on the codebase
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {authors?.slice(0, 10).map((author) => (
            <div key={author.email} className="flex items-center gap-4 p-3 border rounded">
              <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center text-sm font-medium">
                {author.author.split(' ').map(n => n[0]).join('').toUpperCase()}
              </div>
              <div className="flex-1">
                <div className="font-medium">{author.author}</div>
                <div className="text-sm text-muted-foreground">{author.email}</div>
              </div>
              <div className="text-right">
                <div className="font-medium">{author.commits} commits</div>
                <div className="text-sm text-muted-foreground">
                  +{author.lines_added} -{author.lines_deleted}
                </div>
                <Badge variant="outline" className="text-xs">
                  {author.files_modified} files
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}