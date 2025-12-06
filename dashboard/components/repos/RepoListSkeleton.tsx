import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function RepoListSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i} className="animate-pulse">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div className="h-5 bg-muted rounded w-32" />
            <div className="h-5 bg-muted rounded w-16" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 text-sm">
              <div className="h-4 bg-muted rounded w-16" />
              <div className="h-4 bg-muted rounded w-12" />
              <div className="h-4 bg-muted rounded w-14" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}