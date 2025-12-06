"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RepoCard } from "@/components/repos/RepoCard";
import { AddRepoModal } from "@/components/repos/AddRepoModal";
import { RepoListSkeleton } from "@/components/repos/RepoListSkeleton";
import { Button } from "@/components/ui/button";
import { Plus, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { apiClient } from "@/lib/api";
import { Repo } from "@/types";

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