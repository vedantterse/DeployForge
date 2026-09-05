/**
 * The frame around every signed-in page.
 *
 * The navigation is built from the account's role, not filtered in the view:
 * an administrator runs the platform and does not deploy on it, so "Deploy
 * new" is not a link they see greyed out — it is not part of their product at
 * all. Two roles, two applications, one shell.
 */

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode } from "react";

import { clearToken, type User } from "@/lib/auth";
import { Badge, cx } from "@/components/ui";
import {
  BoxIcon,
  ChartIcon,
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
  exact?: boolean;
};

const STUDENT_NAV: NavItem[] = [
  { href: "/dashboard", label: "My apps", icon: <BoxIcon />, exact: true },
  { href: "/dashboard/new", label: "Deploy new", icon: <RocketIcon /> },
];

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Overview", icon: <ChartIcon />, exact: true },
  { href: "/admin/students", label: "Students", icon: <UsersIcon /> },
  { href: "/admin/deployments", label: "Projects", icon: <BoxIcon /> },
  { href: "/admin/infrastructure", label: "Infrastructure", icon: <ServerIcon /> },
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
  const isAdmin = user.role === "admin";
  const items = isAdmin ? ADMIN_NAV : STUDENT_NAV;

  function logOut() {
    clearToken();
    router.push("/login");
  }

  function isActive(item: NavItem) {
    return item.exact ? pathname === item.href : pathname.startsWith(item.href);
  }

  return (
    <div className="flex min-h-screen">
      {/* --- Sidebar ---------------------------------------------------- */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] lg:flex">
        <div className="flex h-16 items-center gap-2.5 border-b border-[var(--border)] px-5">
          <LogoMark className="h-8 w-8" />
          <div className="min-w-0">
            <p className="truncate font-semibold leading-tight tracking-tight">
              DeployForge
            </p>
            <p className="text-[11px] leading-tight text-[var(--text-dim)]">
              {isAdmin ? "Platform administration" : "Deployment platform"}
            </p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cx(
                "flex items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-colors",
                isActive(item)
                  ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="border-t border-[var(--border)] p-3">
          <div className="rounded-[var(--radius-sm)] bg-[var(--surface-2)] px-3 py-2.5">
            <p className="truncate text-sm font-medium" title={user.email}>
              {user.email}
            </p>
            <div className="mt-1.5 flex items-center justify-between">
              {isAdmin ? (
                <Badge tone="accent">
                  <ShieldIcon className="h-3 w-3" />
                  Administrator
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
        <header className="flex h-16 items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--surface)] px-4 lg:hidden">
          <Link
            href={isAdmin ? "/admin" : "/dashboard"}
            className="flex items-center gap-2 font-semibold"
          >
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
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cx(
                "flex shrink-0 items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium",
                isActive(item)
                  ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                  : "text-[var(--text-muted)]",
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          ))}
        </nav>

        <main className="flex-1 px-4 py-8 sm:px-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
