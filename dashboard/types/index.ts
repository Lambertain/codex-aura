export interface Repo {
  id: string;
  name: string;
  url: string;
  branch: string;
  sync_status: 'synced' | 'syncing' | 'stale' | 'error';
  file_count: number;
  last_sync_at: string;
}

export interface GraphNode {
  id: string;
  fqn: string;
  name: string;
  type: 'file' | 'class' | 'function';
  file_path: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: 'IMPORTS' | 'CALLS' | 'EXTENDS';
}