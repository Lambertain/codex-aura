import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

export function useRepos() {
  return useQuery({
    queryKey: ["repos"],
    queryFn: () => apiClient("/api/v1/repos"),
  });
}

export function useRepo(id: string) {
  return useQuery({
    queryKey: ["repo", id],
    queryFn: () => apiClient(`/api/v1/repos/${id}`),
    enabled: !!id,
  });
}