import { useUser } from "@/hooks/useUser";

export default function DashboardPage() {
  const { user, isLoading } = useUser();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2">Welcome</h2>
          <p className="text-gray-600">
            Hello, {user?.name || "User"}! Welcome to Codex Aura.
          </p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2">Plan</h2>
          <p className="text-gray-600">Current plan: {user?.plan || "Free"}</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2">Repositories</h2>
          <p className="text-gray-600">Manage your repositories</p>
        </div>
      </div>
    </div>
  );
}