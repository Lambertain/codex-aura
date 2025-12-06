"use client";

import { UserButton } from "@clerk/nextjs";

export function Header() {
  return (
    <header className="flex h-16 items-center justify-between px-4 bg-white border-b">
      <div></div>
      <UserButton afterSignOutUrl="/" />
    </header>
  );
}