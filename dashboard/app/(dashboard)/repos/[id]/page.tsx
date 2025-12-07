"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  GitBranch,
  FileText,
  AlertCircle,
  CheckCircle,
  Clock,
  Database,
  Zap,
  TrendingUp,
  Users,
  Code
} from "lucide-react";
import { apiClient } from "@/lib/api";
import Link from "next/link";

interface GraphStats {
  node_types: { [key: string]: number };
  edge_types: { [key: string]: number };
}

interface SyncStatus {
  state: 'idle' | 'syncing' | 'completed' | 'failed';
  last_sync_at?: string;
  progress?: number;
  error?: string;
}

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  checks: {
    database: boolean;
    redis: boolean;
    storage: boolean;
  };
}

export default function RepoOverviewPage() {
  const { id: repoId } = useParams();

  // Fetch graph data for stats
  const { data: graphData, isLoading: graphLoading } = useQuery({
    queryKey: ["graph", repoId],
    queryFn: () => apiClient(`/api/v1/graph/${repoId}`),
  });

  // Fetch sync status
  const { data: syncStatus, isLoading: syncLoading } = useQuery({
    queryKey: ["sync-status", repoId],
    queryFn: () => apiClient(`/api/v1/repos/${repoId}/sync/status`),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch health status
  const { data: healthStatus, isLoading: healthLoading } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient("/health/deep"),
  });

  const stats = graphData?.stats as GraphStats;
  const sync = syncStatus as SyncStatus;
  const health = healthStatus as HealthStatus;

  const getSyncStatusColor = (state: string) => {
    switch (state) {
      case 'syncing': return 'bg-blue-500';
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getSyncStatusIcon = (state: string) => {
    switch (state) {
      case 'syncing': return <Clock className="w-4 h-4" />;
      case 'completed': return <CheckCircle className="w-4 h-4" />;
      case 'failed': return <AlertCircle className="w-4 h-4" />;
      default: return <Activity className="w-4 h-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">{graphData?.repo_name || 'Repository Overview'}</h1>
          <p className="text-muted-foreground">Real-time insights into your codebase</p>
        </div>
        <div className="flex gap-2">
          <Link href={`/repos/${repoId}/search`}>
            <Button variant="outline">
              <Code className="w-4 h-4 mr-2" />
              Search Code
            </Button>
          </Link>
          <Button
            onClick={() => apiClient(`/api/v1/repos/${repoId}/sync/trigger`, { method: 'POST' })}
            disabled={sync?.state === 'syncing'}
          >
            <Zap className="w-4 h-4 mr-2" />
            {sync?.state === 'syncing' ? 'Syncing...' : 'Sync Now'}
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Files</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.node_types?.file || 0}</div>
            <p className="text-xs text-muted-foreground">Source files analyzed</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Functions</CardTitle>
            <Code className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.node_types?.function || 0}</div>
            <p className="text-xs text-muted-foreground">Functions detected</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Classes</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.node_types?.class || 0}</div>
            <p className="text-xs text-muted-foreground">Classes defined</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Connections</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{graphData?.edges?.length || 0}</div>
            <p className="text-xs text-muted-foreground">Code relationships</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <div className="space-y-6">
        {/* Overview Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Graph Statistics */}
          <Card>
            <CardHeader>
              <CardTitle>Graph Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm">Total Nodes</span>
                  <span className="font-medium">{graphData?.nodes?.length || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Total Edges</span>
                  <span className="font-medium">{graphData?.edges?.length || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Import Relationships</span>
                  <span className="font-medium">{stats?.edge_types?.IMPORTS || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Function Calls</span>
                  <span className="font-medium">{stats?.edge_types?.CALLS || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Inheritance</span>
                  <span className="font-medium">{stats?.edge_types?.EXTENDS || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Codebase Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Codebase Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Repository</span>
                  <Badge variant="outline">{graphData?.repo_name}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Last Updated</span>
                  <span className="text-sm text-muted-foreground">
                    {graphData?.created_at ? new Date(graphData.created_at).toLocaleString() : 'Never'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Graph ID</span>
                  <code className="text-xs bg-muted px-2 py-1 rounded">{repoId}</code>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Analysis Status</span>
                  <Badge variant="secondary">Completed</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sync Status Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {getSyncStatusIcon(sync?.state || 'idle')}
              Sync Status
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span>Current State</span>
              <Badge className={getSyncStatusColor(sync?.state || 'idle')}>
                {sync?.state || 'idle'}
              </Badge>
            </div>

            {sync?.last_sync_at && (
              <div className="flex items-center justify-between">
                <span>Last Sync</span>
                <span className="text-sm text-muted-foreground">
                  {new Date(sync.last_sync_at).toLocaleString()}
                </span>
              </div>
            )}

            {sync?.progress !== undefined && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Progress</span>
                  <span>{Math.round(sync.progress * 100)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${sync.progress * 100}%` }}
                  ></div>
                </div>
              </div>
            )}

            {sync?.error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded">
                <p className="text-sm text-red-800">{sync.error}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Health Indicators Section */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Health Indicators</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Database</CardTitle>
                {health?.checks?.database ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                )}
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {health?.checks?.database ? 'Connected' : 'Disconnected'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Redis</CardTitle>
                {health?.checks?.redis ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                )}
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {health?.checks?.redis ? 'Connected' : 'Disconnected'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Storage</CardTitle>
                {health?.checks?.storage ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                )}
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {health?.checks?.storage ? 'Healthy' : 'Issues detected'}
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}