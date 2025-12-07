"use client";

import { useState, useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Search,
  Loader2,
  FileText,
  Code,
  ChevronDown,
  ChevronRight,
  Clock,
  Filter
} from "lucide-react";
import { apiClient } from "@/lib/api";

interface SearchResult {
  fqn: string;
  name: string;
  type: string;
  file_path: string;
  score: number;
  snippet: string;
}

export default function SearchPage() {
  const { id: repoId } = useParams();
  const [query, setQuery] = useState("");
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());
  const [searchStartTime, setSearchStartTime] = useState<number>(0);

  const search = useMutation({
    mutationFn: async (q: string) => {
      setSearchStartTime(Date.now());
      const result = await apiClient(`/api/v1/repos/${repoId}/search`, {
        method: "POST",
        body: JSON.stringify({ query: q, mode: "hybrid", limit: 20 }),
      });
      return result;
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      search.mutate(query);
    }
  };

  const toggleExpanded = (fqn: string) => {
    const newExpanded = new Set(expandedResults);
    if (newExpanded.has(fqn)) {
      newExpanded.delete(fqn);
    } else {
      newExpanded.add(fqn);
    }
    setExpandedResults(newExpanded);
  };

  const getRelevanceColor = (score: number) => {
    if (score >= 0.8) return "bg-green-500";
    if (score >= 0.6) return "bg-yellow-500";
    if (score >= 0.4) return "bg-orange-500";
    return "bg-red-500";
  };

  const getRelevanceLabel = (score: number) => {
    if (score >= 0.8) return "High";
    if (score >= 0.6) return "Medium";
    if (score >= 0.4) return "Low";
    return "Poor";
  };

  const searchDuration = useMemo(() => {
    if (!search.data || searchStartTime === 0) return 0;
    return Date.now() - searchStartTime;
  }, [search.data, searchStartTime]);

  const renderCodePreview = (result: SearchResult) => {
    const isExpanded = expandedResults.has(result.fqn);

    return (
      <div className="mt-3 border rounded-lg overflow-hidden">
        <div
          className="flex items-center justify-between p-2 bg-muted/50 cursor-pointer hover:bg-muted/70 transition-colors"
          onClick={() => toggleExpanded(result.fqn)}
        >
          <div className="flex items-center gap-2">
            <Code className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">Code Preview</span>
          </div>
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
        {isExpanded && (
          <pre className="p-3 text-sm bg-muted/30 overflow-x-auto border-t">
            <code>{result.snippet}</code>
          </pre>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Semantic Code Search</h1>
          <p className="text-muted-foreground">Find code using natural language queries</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="w-4 h-4" />
          {searchDuration > 0 && (
            <span>{searchDuration}ms</span>
          )}
        </div>
      </div>

      {/* Search Form */}
      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-5 w-5 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search for functions, classes, or describe functionality..."
                className="pl-12 h-12 text-lg"
                disabled={search.isPending}
              />
            </div>
            <div className="flex gap-3">
              <Button
                type="submit"
                disabled={search.isPending || !query.trim()}
                size="lg"
                className="px-8"
              >
                {search.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4 mr-2" />
                    Search
                  </>
                )}
              </Button>
              <Button variant="outline" size="lg">
                <Filter className="w-4 h-4 mr-2" />
                Filters
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {search.data && (
        <div className="space-y-4">
          {/* Results Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-muted-foreground" />
              <span className="text-lg font-semibold">
                {search.data.total} results found
              </span>
            </div>
            <div className="text-sm text-muted-foreground">
              Search completed in {searchDuration}ms
            </div>
          </div>

          {/* Results List */}
          <div className="space-y-3">
            {search.data.results.map((result: SearchResult, index: number) => (
              <Card key={result.fqn} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  {/* Result Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-xs">
                          {result.type}
                        </Badge>
                        <Badge
                          className={`text-xs text-white ${getRelevanceColor(result.score)}`}
                        >
                          {getRelevanceLabel(result.score)} relevance
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {Math.round(result.score * 100)}% match
                        </span>
                      </div>
                      <h3 className="font-semibold text-lg truncate">{result.name}</h3>
                      <p className="text-sm text-muted-foreground truncate">
                        {result.file_path}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <span className="text-sm font-medium text-muted-foreground">
                        #{index + 1}
                      </span>
                    </div>
                  </div>

                  {/* Relevance Bar */}
                  <div className="mb-3">
                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                      <span>Relevance</span>
                      <span>{Math.round(result.score * 100)}%</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-300 ${getRelevanceColor(result.score)}`}
                        style={{ width: `${result.score * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Code Preview */}
                  {renderCodePreview(result)}
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Load More */}
          {search.data.total > search.data.results.length && (
            <div className="text-center">
              <Button variant="outline">
                Load More Results
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!search.data && !search.isPending && (
        <Card>
          <CardContent className="p-12 text-center">
            <Search className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Search Your Codebase</h3>
            <p className="text-muted-foreground">
              Use natural language to find functions, classes, and code patterns.
              Try queries like "authentication logic" or "database connection handling".
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}