"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentUser, type User } from "@/lib/auth";
import NavBar from "@/components/NavBar";

/**
 * Wraps the authenticated area: resolves the current user from /auth/me and
 * sends anonymous visitors to the login page.
 *
 * This is convenience, not security — the backend rejects unauthenticated and
 * under-privileged requests regardless of what the browser renders.
 */
export default function RequireAuth({
  children,
}: {
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
      setUser(u);
      setChecked(true);
    });
    return () => {
      active = false;
    };
  }, [router]);

  if (!checked || !user) {
    return (
      <main className="flex flex-1 items-center justify-center p-8 text-sm text-slate-500">
        Loading…
      </main>
    );
  }

  return (
    <>
      <NavBar user={user} />
      {children(user)}
    </>
  );
}
