export default function DashboardPage() {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2">Welcome</h2>
          <p className="text-gray-600">Welcome to Codex Aura Dashboard!</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2">Repositories</h2>
          <p className="text-gray-600">Manage your repositories</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-2">Analytics</h2>
          <p className="text-gray-600">View usage analytics</p>
        </div>
      </div>
    </div>
  );
}