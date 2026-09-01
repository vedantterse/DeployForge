"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearToken, type User } from "@/lib/auth";

/** Top bar for the authenticated area. */
export default function NavBar({ user }: { user: User }) {
  const router = useRouter();

  function logOut() {
    clearToken();
    router.push("/login");
  }

  return (
    <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <nav className="mx-auto flex max-w-4xl items-center justify-between gap-4 p-4">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="font-bold">
            DeployForge
          </Link>
          <Link
            href="/dashboard"
            className="text-sm text-slate-600 hover:underline dark:text-slate-300"
          >
            Dashboard
          </Link>
          <Link
            href="/dashboard/new"
            className="text-sm text-slate-600 hover:underline dark:text-slate-300"
          >
            New deployment
          </Link>
          {user.role === "admin" && (
            <Link
              href="/admin"
              className="text-sm text-slate-600 hover:underline dark:text-slate-300"
            >
              Admin
            </Link>
          )}
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-slate-600 dark:text-slate-300">{user.email}</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide dark:bg-slate-800">
            {user.role}
          </span>
          <button
            onClick={logOut}
            className="rounded-md border border-slate-300 px-3 py-1.5 font-medium transition hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            Log out
          </button>
        </div>
      </nav>
    </header>
  );
}
