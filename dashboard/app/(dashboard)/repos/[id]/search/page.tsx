"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";

export default function SearchPage() {
  const { id: repoId } = useParams();
  const [query, setQuery] = useState("");

  const search = useMutation({
    mutationFn: (q: string) =>
      apiClient(`/api/v1/repos/${repoId}/search`, {
        method: "POST",
        body: JSON.stringify({ query: q, mode: "hybrid", limit: 20 }),
      }),
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      search.mutate(query);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Search Code</h1>

      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Describe what you're looking for..."
            className="pl-10"
          />
        </div>
        <Button type="submit" disabled={search.isPending}>
          {search.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Search"}
        </Button>
      </form>

      {search.data && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Found {search.data.total} results
          </p>

          {search.data.results.map((result: any) => (
            <Card key={result.fqn}>
              <CardContent className="p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-medium">{result.name}</h3>
                    <p className="text-sm text-muted-foreground">{result.file_path}</p>
                  </div>
                  <Badge>{Math.round(result.score * 100)}% match</Badge>
                </div>
                <pre className="mt-2 text-sm bg-muted p-2 rounded overflow-x-auto">
                  {result.snippet}
                </pre>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}