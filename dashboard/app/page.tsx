import Link from "next/link";

export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900">Codex Aura</h1>
          <p className="mt-2 text-gray-600">Repository Analysis Dashboard</p>
        </div>
        <div className="text-center">
          <Link href="/dashboard" className="text-sm text-blue-600 hover:text-blue-500">
            Continue to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
