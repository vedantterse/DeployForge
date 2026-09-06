/**
 * The frame around every signed-in page.
 *
 * The navigation is built from the account's role rather than filtered in the
 * view: an administrator runs the platform and does not deploy on it, so
 * "Deploy new" is not a link they see greyed out — it is not part of their
 * product at all. Two roles, two applications, one shell.
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
    <div className="flex min-h-screen bg-[var(--bg-deep)]">
      {/* --- Sidebar ---------------------------------------------------- */}
      <aside className="sticky top-0 hidden h-screen w-[17rem] shrink-0 flex-col p-3 lg:flex">
        <div className="plate flex h-full flex-col rounded-[var(--r-lg)]">
          <div className="flex h-[4.25rem] items-center gap-3 border-b border-[var(--hairline)] px-5">
            <LogoMark className="h-9 w-9" />
            <div className="min-w-0">
              <p className="truncate text-[15px] font-semibold leading-tight">
                DeployForge
              </p>
              <p className="text-[11px] leading-tight text-[var(--text-dim)]">
                {isAdmin ? "Platform administration" : "Deployment platform"}
              </p>
            </div>
          </div>

          <nav className="flex-1 space-y-1 p-3">
            {items.map((item) => {
              const active = isActive(item);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "group relative flex items-center gap-3 rounded-[var(--r-sm)] px-3 py-2.5 text-sm font-medium",
                    "transition-[color,background-color] duration-[var(--t-hover)] ease-[var(--ease-out)]",
                    active
                      ? "bg-[var(--surface-2)] text-[var(--text)]"
                      : "text-[var(--text-muted)] hover:bg-[var(--surface-2)]/60 hover:text-[var(--text)]",
                  )}
                >
                  {/* The active route is marked by a copper rule, not a block
                      of brand colour — quieter, and it survives being next to
                      four status hues. */}
                  <span
                    aria-hidden
                    className={cx(
                      "absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full bg-[var(--accent)]",
                      "transition-opacity duration-[var(--t-hover)]",
                      active ? "opacity-100" : "opacity-0",
                    )}
                  />
                  <span className={active ? "text-[var(--accent)]" : undefined}>
                    {item.icon}
                  </span>
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="p-3">
            <div className="rounded-[var(--r-sm)] border border-[var(--hairline)] bg-[var(--surface-2)] px-3.5 py-3 shadow-[var(--bevel)]">
              <p className="truncate text-sm font-medium" title={user.email}>
                {user.email}
              </p>
              <div className="mt-2 flex items-center justify-between gap-2">
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
                  className="text-xs text-[var(--text-dim)] transition-colors duration-[var(--t-hover)] hover:text-[var(--danger)]"
                >
                  Log out
                </button>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* --- Content ---------------------------------------------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile chrome. Glass, and fixed — backdrop-filter belongs only on
            elements that do not scroll. */}
        <header className="glass sticky top-0 z-20 flex h-16 items-center justify-between gap-4 px-4 lg:hidden">
          <Link
            href={isAdmin ? "/admin" : "/dashboard"}
            className="flex items-center gap-2.5 font-semibold"
          >
            <LogoMark className="h-8 w-8" />
            DeployForge
          </Link>
          <button
            onClick={logOut}
            className="text-sm text-[var(--text-muted)] transition-colors hover:text-[var(--danger)]"
          >
            Log out
          </button>
        </header>

        <nav className="sticky top-16 z-10 flex gap-1.5 overflow-x-auto border-b border-[var(--hairline)] bg-[var(--bg)] px-3 py-2.5 lg:hidden">
          {items.map((item) => {
            const active = isActive(item);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cx(
                  "flex shrink-0 items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-medium",
                  "transition-colors duration-[var(--t-hover)]",
                  active
                    ? "border-[var(--accent-line)] bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "border-[var(--hairline)] text-[var(--text-muted)]",
                )}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>

        <main className="flex-1 px-4 py-8 sm:px-8 lg:py-10 lg:pl-2 lg:pr-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
