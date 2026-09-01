"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import { apiFetch, ApiError } from "@/lib/api";
import type { User } from "@/lib/auth";

type Stats = {
  users: number;
  admins: number;
  github_connections: number;
  repositories: number;
  deployments: number;
};

/**
 * Admin-only page.
 *
 * The data is fetched from /admin/*, which is gated by require_admin on the
 * backend. A normal user reaching this URL gets a 403 from the API and sees
 * the refusal below — the page cannot show them the data by mistake, because
 * it never has it.
 */
function AdminContent() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(
    null,
  );

  useEffect(() => {
    Promise.all([apiFetch<Stats>("/admin/stats"), apiFetch<User[]>("/admin/users")])
      .then(([s, u]) => {
        setStats(s);
        setUsers(u);
      })
      .catch((err) =>
        setError({
          status: err instanceof ApiError ? err.status : 0,
          message: err instanceof Error ? err.message : "Request failed",
        }),
      );
  }, []);

  if (error) {
    return (
      <main className="mx-auto w-full max-w-4xl flex-1 p-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 dark:border-red-900 dark:bg-red-950">
          <h1 className="text-lg font-semibold text-red-800 dark:text-red-200">
            {error.status === 403 ? "Administrator access required" : "Error"}
          </h1>
          <p className="mt-1 text-sm text-red-700 dark:text-red-300">
            {error.message}
          </p>
          <p className="mt-3 text-xs text-red-600 dark:text-red-400">
            The backend refused this request with HTTP {error.status}. Role
            checks run on the server, not in the browser.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold">Admin</h1>
        <p className="mt-1 text-slate-600 dark:text-slate-400">
          Platform-wide view. Visible only to accounts with the admin role.
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h2 className="font-semibold">Platform stats</h2>
        {stats ? (
          <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-5">
            {Object.entries(stats).map(([key, value]) => (
              <div key={key}>
                <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  {key.replace(/_/g, " ")}
                </dt>
                <dd className="text-2xl font-semibold">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Loading…</p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h2 className="font-semibold">All users</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
              <tr>
                <th className="py-2 pr-4">Email</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2 pr-4">Active</th>
                <th className="py-2">Joined</th>
              </tr>
            </thead>
            <tbody>
              {(users ?? []).map((u) => (
                <tr
                  key={u.id}
                  className="border-t border-slate-100 dark:border-slate-800"
                >
                  <td className="py-2 pr-4 font-mono">{u.email}</td>
                  <td className="py-2 pr-4">{u.role}</td>
                  <td className="py-2 pr-4">{String(u.is_active)}</td>
                  <td className="py-2">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users?.length === 0 && (
            <p className="mt-2 text-sm text-slate-500">No users yet.</p>
          )}
        </div>
      </section>
    </main>
  );
}

export default function AdminPage() {
  return <RequireAuth>{() => <AdminContent />}</RequireAuth>;
}
