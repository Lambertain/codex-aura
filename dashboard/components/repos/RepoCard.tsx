import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GitBranch, Clock, FileCode } from "lucide-react";
import Link from "next/link";
import { Repo } from "@/types";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

interface RepoCardProps {
  repo: Repo;
}

export function RepoCard({ repo }: RepoCardProps) {
  const syncStatus = {
    synced: { color: "bg-green-500", label: "Synced" },
    syncing: { color: "bg-yellow-500", label: "Syncing" },
    stale: { color: "bg-orange-500", label: "Stale" },
    error: { color: "bg-red-500", label: "Error" },
  }[repo.sync_status];

  return (
    <Link href={`/repos/${repo.id}`}>
      <Card className="hover:border-primary transition-colors cursor-pointer">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-lg">{repo.name}</CardTitle>
          <Badge variant="outline" className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${syncStatus.color}`} />
            {syncStatus.label}
          </Badge>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-1">
              <FileCode className="w-4 h-4" />
              {repo.file_count} files
            </div>
            <div className="flex items-center gap-1">
              <GitBranch className="w-4 h-4" />
              {repo.branch}
            </div>
            <div className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {formatRelativeTime(repo.last_sync_at)}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}