# 📋 Phase 2.4: Dashboard & Billing

---

## E7: 📊 Dashboard (Детальная реализация)

### E7-1: Tech Stack & Project Setup
**Оценка:** 2h | **Приоритет:** P1

### Описание
Настройка Next.js проекта для dashboard.

### Setup

```bash
# Create Next.js project
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app

# Install dependencies
cd dashboard
npm install @tanstack/react-query axios zustand
npm install @radix-ui/react-dialog @radix-ui/react-dropdown-menu
npm install lucide-react recharts
npm install d3 @types/d3  # for graph visualization

# shadcn/ui setup
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card input table dialog
```

### Project Structure

```
dashboard/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                    # Landing / Dashboard home
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx              # Dashboard layout with sidebar
│   │   ├── repos/
│   │   │   ├── page.tsx            # Repository list
│   │   │   └── [id]/
│   │   │       ├── page.tsx        # Repo overview
│   │   │       ├── graph/page.tsx  # Graph visualization
│   │   │       ├── search/page.tsx # Search interface
│   │   │       └── settings/page.tsx
│   │   ├── settings/
│   │   │   ├── page.tsx            # General settings
│   │   │   ├── billing/page.tsx
│   │   │   └── api-keys/page.tsx
│   │   └── usage/page.tsx          # Usage analytics
├── components/
│   ├── ui/                         # shadcn components
│   ├── graph/
│   │   ├── GraphVisualization.tsx
│   │   ├── NodeDetailsPanel.tsx
│   │   └── GraphControls.tsx
│   ├── repos/
│   │   ├── RepoCard.tsx
│   │   ├── RepoList.tsx
│   │   └── AddRepoModal.tsx
│   └── layout/
│       ├── Sidebar.tsx
│       ├── Header.tsx
│       └── UserMenu.tsx
├── lib/
│   ├── api.ts                      # API client
│   ├── auth.ts                     # Auth utilities
│   └── utils.ts
├── hooks/
│   ├── useRepos.ts
│   ├── useGraph.ts
│   └── useUser.ts
└── stores/
    └── graph-store.ts              # Zustand store for graph state
```

### Критерии приёмки
- [ ] Next.js 14 с App Router
- [ ] TailwindCSS + shadcn/ui
- [ ] TypeScript strict mode
- [ ] React Query для data fetching

---

### E7-2: Authentication (Clerk)
**Оценка:** 3h | **Приоритет:** P0

### Реализация

```typescript
// app/layout.tsx
import { ClerkProvider } from '@clerk/nextjs'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>{children}</body>
      </html>
    </ClerkProvider>
  )
}

// middleware.ts
import { authMiddleware } from "@clerk/nextjs";

export default authMiddleware({
  publicRoutes: ["/", "/api/webhooks(.*)"],
});

export const config = {
  matcher: ["/((?!.+\\.[\\w]+$|_next).*)", "/", "/(api|trpc)(.*)"],
};

// lib/api.ts
import { auth } from "@clerk/nextjs";

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const { getToken } = auth();
  const token = await getToken();
  
  const response = await fetch(`${process.env.API_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}

// hooks/useUser.ts
import { useUser as useClerkUser } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";

export function useUser() {
  const { user: clerkUser, isLoaded } = useClerkUser();
  
  const { data: userData } = useQuery({
    queryKey: ["user", clerkUser?.id],
    queryFn: () => apiClient("/api/v1/users/me"),
    enabled: isLoaded && !!clerkUser,
  });
  
  return {
    user: userData,
    isLoading: !isLoaded,
    plan: userData?.plan || "free",
  };
}
```

### Критерии приёмки
- [ ] Sign up / Sign in работает
- [ ] JWT токены передаются в API
- [ ] Protected routes
- [ ] User profile sync с backend

---

### E7-3: Repository List View
**Оценка:** 3h | **Приоритет:** P0

### Реализация

```typescript
// app/(dashboard)/repos/page.tsx
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RepoCard } from "@/components/repos/RepoCard";
import { AddRepoModal } from "@/components/repos/AddRepoModal";
import { Button } from "@/components/ui/button";
import { Plus, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useState } from "react";

export default function ReposPage() {
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  
  const { data: repos, isLoading } = useQuery({
    queryKey: ["repos"],
    queryFn: () => apiClient<Repo[]>("/api/v1/repos"),
  });
  
  const filteredRepos = repos?.filter(repo => 
    repo.name.toLowerCase().includes(search.toLowerCase())
  );
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Repositories</h1>
        <Button onClick={() => setShowAddModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Add Repository
        </Button>
      </div>
      
      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search repositories..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>
      
      {isLoading ? (
        <RepoListSkeleton />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredRepos?.map((repo) => (
            <RepoCard key={repo.id} repo={repo} />
          ))}
        </div>
      )}
      
      <AddRepoModal 
        open={showAddModal} 
        onClose={() => setShowAddModal(false)} 
      />
    </div>
  );
}

// components/repos/RepoCard.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GitBranch, Clock, FileCode } from "lucide-react";
import Link from "next/link";

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

// components/repos/AddRepoModal.tsx
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function AddRepoModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [url, setUrl] = useState("");
  const queryClient = useQueryClient();
  
  const addRepo = useMutation({
    mutationFn: (repoUrl: string) => 
      apiClient("/api/v1/repos", {
        method: "POST",
        body: JSON.stringify({ url: repoUrl }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      onClose();
      setUrl("");
    },
  });
  
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Repository</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="repo-url">Repository URL</Label>
            <Input
              id="repo-url"
              placeholder="https://github.com/owner/repo"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <Button 
            onClick={() => addRepo.mutate(url)}
            disabled={addRepo.isPending || !url}
            className="w-full"
          >
            {addRepo.isPending ? "Adding..." : "Add Repository"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

### Критерии приёмки
- [ ] Список репозиториев загружается
- [ ] Поиск по названию
- [ ] Статус синхронизации отображается
- [ ] Добавление нового репозитория
- [ ] Skeleton loading states

---

### E7-4: Graph Visualization
**Оценка:** 6h | **Приоритет:** P1

### Реализация

```typescript
// components/graph/GraphVisualization.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { useGraph } from "@/hooks/useGraph";

interface GraphNode {
  id: string;
  fqn: string;
  name: string;
  type: "file" | "class" | "function";
  file_path: string;
}

interface GraphEdge {
  source: string;
  target: string;
  type: "IMPORTS" | "CALLS" | "EXTENDS";
}

interface GraphVisualizationProps {
  repoId: string;
  onNodeSelect: (node: GraphNode | null) => void;
  selectedNode: GraphNode | null;
}

export function GraphVisualization({ 
  repoId, 
  onNodeSelect,
  selectedNode 
}: GraphVisualizationProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  const { data: graphData, isLoading } = useGraph(repoId);
  
  useEffect(() => {
    if (!graphData || !svgRef.current || !containerRef.current) return;
    
    const svg = d3.select(svgRef.current);
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    // Clear previous
    svg.selectAll("*").remove();
    
    // Setup zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });
    
    svg.call(zoom);
    
    const g = svg.append("g");
    
    // Color scale for node types
    const colorScale = d3.scaleOrdinal<string>()
      .domain(["file", "class", "function"])
      .range(["#6366f1", "#8b5cf6", "#a855f7"]);
    
    // Edge color scale
    const edgeColorScale = d3.scaleOrdinal<string>()
      .domain(["IMPORTS", "CALLS", "EXTENDS"])
      .range(["#94a3b8", "#22c55e", "#f59e0b"]);
    
    // Force simulation
    const simulation = d3.forceSimulation(graphData.nodes as d3.SimulationNodeDatum[])
      .force("link", d3.forceLink(graphData.edges)
        .id((d: any) => d.id)
        .distance(100))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(30));
    
    // Draw edges
    const link = g.append("g")
      .selectAll("line")
      .data(graphData.edges)
      .join("line")
      .attr("stroke", d => edgeColorScale(d.type))
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", 1.5);
    
    // Draw nodes
    const node = g.append("g")
      .selectAll("g")
      .data(graphData.nodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(d3.drag<any, GraphNode>()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));
    
    // Node circles
    node.append("circle")
      .attr("r", d => d.type === "file" ? 20 : d.type === "class" ? 15 : 10)
      .attr("fill", d => colorScale(d.type))
      .attr("stroke", "#fff")
      .attr("stroke-width", 2);
    
    // Node labels
    node.append("text")
      .text(d => d.name.length > 15 ? d.name.slice(0, 15) + "..." : d.name)
      .attr("x", 0)
      .attr("y", d => (d.type === "file" ? 20 : d.type === "class" ? 15 : 10) + 15)
      .attr("text-anchor", "middle")
      .attr("font-size", "10px")
      .attr("fill", "#64748b");
    
    // Click handler
    node.on("click", (event, d) => {
      event.stopPropagation();
      onNodeSelect(d);
    });
    
    // Background click to deselect
    svg.on("click", () => onNodeSelect(null));
    
    // Highlight selected node
    node.attr("opacity", d => 
      selectedNode ? (d.id === selectedNode.id ? 1 : 0.3) : 1
    );
    
    // Simulation tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);
      
      node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });
    
    // Drag functions
    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }
    
    function dragged(event: any) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }
    
    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }
    
    return () => {
      simulation.stop();
    };
  }, [graphData, selectedNode, onNodeSelect]);
  
  if (isLoading) {
    return <div className="flex items-center justify-center h-full">Loading graph...</div>;
  }
  
  return (
    <div ref={containerRef} className="w-full h-full">
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
```

### Критерии приёмки
- [ ] D3.js force-directed graph
- [ ] Zoom и pan
- [ ] Drag nodes
- [ ] Click для select
- [ ] Цвета по типу node/edge
- [ ] Labels на nodes
- [ ] Highlight selected

---

### E7-5: Node Details Panel
**Оценка:** 3h | **Приоритет:** P1

```typescript
// components/graph/NodeDetailsPanel.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Copy, ExternalLink, GitBranch, FileCode } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

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
            <label className="text-sm font-medium">Code</label>
            <div className="mt-1 rounded overflow-hidden max-h-64">
              <SyntaxHighlighter
                language="python"
                style={vscDarkPlus}
                customStyle={{ margin: 0, fontSize: "12px" }}
              >
                {nodeDetails.content}
              </SyntaxHighlighter>
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
```

---

### E7-6: Search Interface
**Оценка:** 3h | **Приоритет:** P1

```typescript
// app/(dashboard)/repos/[id]/search/page.tsx
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Search, Loader2 } from "lucide-react";

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
```

---

### E7-7 до E7-10: Остальные Dashboard компоненты

Краткое описание (реализация аналогична):

- **E7-7: Hotspot Map** — Heatmap визуализация часто изменяемого кода (требует Git Integration)
- **E7-8: Code Authorship** — Показ авторов по файлам (требует Git Blame)
- **E7-9: API Usage Stats** — Графики использования API (recharts)
- **E7-10: Settings & Billing Portal** — Управление настройками и подпиской

---

## E8: 💳 Billing System

### E8-1: Stripe Integration
**Оценка:** 4h | **Приоритет:** P1

```python
# src/codex_aura/billing/stripe_client.py

import stripe
from pydantic import BaseModel

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeClient:
    """Stripe integration for billing."""
    
    async def create_customer(self, user: User) -> str:
        """Create Stripe customer for user."""
        customer = stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={"user_id": user.id}
        )
        return customer.id
    
    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str
    ) -> str:
        """Create Checkout session for subscription."""
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True
        )
        return session.url
    
    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> str:
        """Create Customer Portal session for managing subscription."""
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )
        return session.url
    
    async def get_subscription(self, subscription_id: str) -> dict:
        """Get subscription details."""
        return stripe.Subscription.retrieve(subscription_id)
    
    async def cancel_subscription(self, subscription_id: str):
        """Cancel subscription at period end."""
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
```

---

### E8-2: Subscription Plans
**Оценка:** 2h | **Приоритет:** P1

```python
# src/codex_aura/billing/plans.py

from dataclasses import dataclass
from enum import Enum

class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"

@dataclass
class PlanLimits:
    repos: int
    requests_per_day: int
    requests_per_month: int
    max_tokens_per_request: int
    team_members: int
    features: list[str]

PLAN_LIMITS: dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        repos=1,
        requests_per_day=100,
        requests_per_month=1000,
        max_tokens_per_request=4000,
        team_members=1,
        features=["basic_search", "graph_view"]
    ),
    PlanTier.PRO: PlanLimits(
        repos=5,
        requests_per_day=1000,
        requests_per_month=10000,
        max_tokens_per_request=16000,
        team_members=1,
        features=["semantic_search", "token_budgeting", "impact_analysis", "api_access"]
    ),
    PlanTier.TEAM: PlanLimits(
        repos=20,
        requests_per_day=5000,
        requests_per_month=50000,
        max_tokens_per_request=32000,
        team_members=10,
        features=["semantic_search", "token_budgeting", "impact_analysis", 
                  "api_access", "team_management", "priority_support"]
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        repos=-1,  # unlimited
        requests_per_day=-1,
        requests_per_month=-1,
        max_tokens_per_request=100000,
        team_members=-1,
        features=["all", "sso", "audit_logs", "sla", "dedicated_support"]
    ),
}

# Stripe Price IDs
STRIPE_PRICES = {
    PlanTier.PRO: "price_pro_monthly",
    PlanTier.TEAM: "price_team_monthly",
}
```

---

### E8-3: Usage Metering
**Оценка:** 3h | **Приоритет:** P1

```python
# src/codex_aura/billing/usage.py

from datetime import datetime, timedelta
from redis import Redis

class UsageTracker:
    """Track API usage for billing and rate limiting."""
    
    def __init__(self, redis: Redis, db: Database):
        self.redis = redis
        self.db = db
    
    async def record_request(
        self,
        user_id: str,
        endpoint: str,
        tokens_used: int
    ):
        """Record API request for usage tracking."""
        now = datetime.utcnow()
        day_key = f"usage:{user_id}:{now.strftime('%Y-%m-%d')}"
        month_key = f"usage:{user_id}:{now.strftime('%Y-%m')}"
        
        # Increment daily counter
        await self.redis.hincrby(day_key, "requests", 1)
        await self.redis.hincrby(day_key, "tokens", tokens_used)
        await self.redis.expire(day_key, 86400 * 7)  # Keep 7 days
        
        # Increment monthly counter
        await self.redis.hincrby(month_key, "requests", 1)
        await self.redis.hincrby(month_key, "tokens", tokens_used)
        await self.redis.expire(month_key, 86400 * 35)  # Keep 35 days
        
        # Async write to DB for permanent storage
        await self.db.insert_usage_event(
            user_id=user_id,
            endpoint=endpoint,
            tokens_used=tokens_used,
            timestamp=now
        )
    
    async def get_usage(self, user_id: str, period: str = "day") -> dict:
        """Get usage for period."""
        now = datetime.utcnow()
        
        if period == "day":
            key = f"usage:{user_id}:{now.strftime('%Y-%m-%d')}"
        else:
            key = f"usage:{user_id}:{now.strftime('%Y-%m')}"
        
        data = await self.redis.hgetall(key)
        return {
            "requests": int(data.get("requests", 0)),
            "tokens": int(data.get("tokens", 0))
        }
    
    async def check_limits(self, user_id: str, plan: PlanTier) -> tuple[bool, str]:
        """Check if user is within plan limits."""
        limits = PLAN_LIMITS[plan]
        
        daily_usage = await self.get_usage(user_id, "day")
        monthly_usage = await self.get_usage(user_id, "month")
        
        if limits.requests_per_day != -1 and daily_usage["requests"] >= limits.requests_per_day:
            return False, "Daily request limit reached"
        
        if limits.requests_per_month != -1 and monthly_usage["requests"] >= limits.requests_per_month:
            return False, "Monthly request limit reached"
        
        return True, ""
```

---

### E8-4: Quota Enforcement Middleware
**Оценка:** 2h | **Приоритет:** P0

```python
# src/codex_aura/api/middleware/quota.py

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class QuotaEnforcementMiddleware(BaseHTTPMiddleware):
    """Enforce plan quotas on API requests."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip for non-API routes
        if not request.url.path.startswith("/api/v1"):
            return await call_next(request)
        
        # Skip for public endpoints
        public_endpoints = ["/api/v1/health", "/api/v1/info"]
        if request.url.path in public_endpoints:
            return await call_next(request)
        
        # Get user from auth
        user = request.state.user
        if not user:
            return await call_next(request)
        
        # Check quotas
        usage_tracker = request.app.state.usage_tracker
        allowed, reason = await usage_tracker.check_limits(user.id, user.plan)
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "quota_exceeded",
                    "message": reason,
                    "upgrade_url": "/settings/billing"
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Record usage (async, don't block response)
        tokens_used = response.headers.get("X-Tokens-Used", 0)
        asyncio.create_task(
            usage_tracker.record_request(user.id, request.url.path, int(tokens_used))
        )
        
        return response
```
