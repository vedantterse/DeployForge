"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";
import { Skeleton } from "@/components/ui";
import { getCurrentUser, type User } from "@/lib/auth";

/**
 * Wraps the authenticated area: resolves the current user from /auth/me and
 * sends anonymous visitors to the login page.
 *
 * This is convenience, not security — the backend rejects unauthenticated and
 * under-privileged requests regardless of what the browser chooses to render.
 */
export default function RequireAuth({
  adminOnly = false,
  studentOnly = false,
  children,
}: {
  adminOnly?: boolean;
  /**
   * Send administrators away. The student area is not a lesser version of the
   * admin console — deploying is not something an administrator does here, so
   * these pages are not theirs to land on, even by typing the URL.
   */
  studentOnly?: boolean;
  children: (user: User) => React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let active = true;
    getCurrentUser().then((u) => {
      if (!active) return;
      if (!u) {
        router.replace("/login");
        return;
      }
      if (adminOnly && u.role !== "admin") {
        router.replace("/dashboard");
        return;
      }
      if (studentOnly && u.role === "admin") {
        router.replace("/admin");
        return;
      }
      setUser(u);
      setChecked(true);
    });
    return () => {
      active = false;
    };
  }, [router, adminOnly, studentOnly]);

  if (!checked || !user) {
    // A skeleton in the final layout, so the page does not jump when it loads.
    return (
      <div className="flex min-h-screen">
        <div className="hidden w-60 shrink-0 border-r border-[var(--hairline)] bg-[var(--surface)] lg:block" />
        <div className="flex-1 px-8 py-8">
          <div className="mx-auto w-full max-w-6xl space-y-6">
            <Skeleton className="h-9 w-56" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-24" />
              ))}
            </div>
            <Skeleton className="h-64" />
          </div>
        </div>
      </div>
    );
  }

  return <AppShell user={user}>{children(user)}</AppShell>;
}
