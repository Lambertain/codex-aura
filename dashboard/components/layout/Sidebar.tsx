"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Dashboard", href: "/" },
  { name: "Repos", href: "/repos" },
  { name: "Settings", href: "/settings" },
  { name: "Usage", href: "/usage" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full w-64 flex-col bg-gray-50">
      <div className="flex h-16 items-center px-4">
        <h1 className="text-xl font-bold">Codex Aura</h1>
      </div>
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navigation.map((item) => (
          <Link
            key={item.name}
            href={item.href}
            className={cn(
              "block px-3 py-2 text-sm font-medium rounded-md",
              pathname === item.href
                ? "bg-gray-200 text-gray-900"
                : "text-gray-600 hover:bg-gray-100"
            )}
          >
            {item.name}
          </Link>
        ))}
      </nav>
    </div>
  );
}