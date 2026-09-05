/**
 * The frame around every signed-in page: sidebar, top bar, content column.
 *
 * A sidebar rather than a top-nav because the product has two distinct modes —
 * a student managing their own apps, and an admin watching everyone's — and a
 * persistent rail makes which one you are in unambiguous.
 */

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode } from "react";

import { clearToken, type User } from "@/lib/auth";
import { Badge, cx } from "@/components/ui";
import {
  BoxIcon,
  LogoMark,
  RocketIcon,
  ServerIcon,
  ShieldIcon,
  UsersIcon,
} from "@/components/Icons";

type NavItem = {
  href: string;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
  exact?: boolean;
};

const NAV: NavItem[] = [
  { href: "/dashboard", label: "My apps", icon: <BoxIcon />, exact: true },
  { href: "/dashboard/new", label: "Deploy new", icon: <RocketIcon /> },
  { href: "/admin", label: "Accounts", icon: <UsersIcon />, adminOnly: true, exact: true },
  { href: "/admin/deployments", label: "All apps", icon: <ServerIcon />, adminOnly: true },
];

export default function AppShell({
  user,
  children,
}: {
  user: User;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();

  function logOut() {
    clearToken();
    router.push("/login");
  }

  const items = NAV.filter((i) => !i.adminOnly || user.role === "admin");

  return (
    <div className="flex min-h-screen">
      {/* --- Sidebar ---------------------------------------------------- */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] lg:flex">
        <div className="flex h-16 items-center gap-2.5 border-b border-[var(--border)] px-5">
          <LogoMark className="h-8 w-8" />
          <span className="font-semibold tracking-tight">DeployForge</span>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {items.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cx(
                  "flex items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
                )}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-[var(--border)] p-3">
          <div className="rounded-[var(--radius-sm)] bg-[var(--surface-2)] px-3 py-2.5">
            <p className="truncate text-sm font-medium" title={user.email}>
              {user.email}
            </p>
            <div className="mt-1.5 flex items-center justify-between">
              {user.role === "admin" ? (
                <Badge tone="accent">
                  <ShieldIcon className="h-3 w-3" />
                  Admin
                </Badge>
              ) : (
                <Badge>Student</Badge>
              )}
              <button
                onClick={logOut}
                className="text-xs text-[var(--text-dim)] transition-colors hover:text-[var(--danger)]"
              >
                Log out
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* --- Content ---------------------------------------------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile bar: the sidebar collapses away below lg. */}
        <header className="flex h-16 items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--surface)] px-4 lg:hidden">
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
            <LogoMark className="h-7 w-7" />
            DeployForge
          </Link>
          <button
            onClick={logOut}
            className="text-sm text-[var(--text-muted)] hover:text-[var(--danger)]"
          >
            Log out
          </button>
        </header>

        <nav className="flex gap-1 overflow-x-auto border-b border-[var(--border)] bg-[var(--surface)] px-3 py-2 lg:hidden">
          {items.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cx(
                  "flex shrink-0 items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium",
                  active
                    ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "text-[var(--text-muted)]",
                )}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>

        <main className="flex-1 px-4 py-8 sm:px-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
