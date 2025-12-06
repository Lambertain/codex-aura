import { useUser as useClerkUser } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

interface UserData {
  name?: string;
  plan?: string;
}

export function useUser() {
  const { user: clerkUser, isLoaded } = useClerkUser();

  const { data: userData } = useQuery<UserData>({
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