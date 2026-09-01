"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import DeploymentTable from "@/components/DeploymentTable";
import RequireAuth from "@/components/RequireAuth";
import {
  listMyDeployments,
  platformOverview,
  type DeploymentRow,
  type UserDeployments,
} from "@/lib/github";
import type { User } from "@/lib/auth";

function StartButton() {
  return (
    <Link
      href="/dashboard/new"
      className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
    >
      Start new deployment
    </Link>
  );
}

/** A normal user's view: their own deployments. */
function MyDeployments() {
  const [rows, setRows] = useState<DeploymentRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listMyDeployments()
      .then((r) => {
        if (active) setRows(r);
      })
      .catch((err: unknown) => {
        if (active)
          setError(err instanceof Error ? err.message : "Could not load deployments.");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <h2 className="font-semibold">Your deployments</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        {rows === null ? "Loading…" : `${rows.length} total`}
      </p>
      <div className="mt-4">
        {error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        ) : (
          rows !== null && (
            <DeploymentTable
              rows={rows}
              emptyMessage="You haven't deployed anything yet."
            />
          )
        )}
      </div>
    </section>
  );
}

/** An admin's view: every account and what each of them deployed. */
function EveryonesDeployments() {
  const [people, setPeople] = useState<UserDeployments[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    platformOverview()
      .then((p) => {
        if (active) setPeople(p);
      })
      .catch((err: unknown) => {
        if (active)
          setError(err instanceof Error ? err.message : "Could not load the overview.");
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
        {error}
      </p>
    );
  }

  if (people === null) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>;
  }

  const totalDeployments = people.reduce((n, p) => n + p.deployment_count, 0);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">All users and their deployments</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {people.length} {people.length === 1 ? "account" : "accounts"} ·{" "}
          {totalDeployments} {totalDeployments === 1 ? "deployment" : "deployments"}
        </p>
      </div>

      {people.map((person) => (
        <div
          key={person.id}
          className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium">{person.email}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide dark:bg-slate-800">
                  {person.role}
                </span>
                {!person.is_active && (
                  <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800 dark:bg-red-950 dark:text-red-200">
                    disabled
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {person.github_username
                  ? `GitHub: @${person.github_username}`
                  : "GitHub not connected"}
                {" · "}
                {person.repository_count}{" "}
                {person.repository_count === 1 ? "target" : "targets"}
                {" · joined "}
                {new Date(person.created_at).toLocaleDateString()}
              </p>
            </div>
            <span className="text-sm text-slate-500 dark:text-slate-400">
              {person.deployment_count}{" "}
              {person.deployment_count === 1 ? "deployment" : "deployments"}
            </span>
          </div>

          {person.deployments.length > 0 ? (
            <div className="mt-4">
              <DeploymentTable rows={person.deployments} />
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
              Nothing deployed yet.
            </p>
          )}
        </div>
      ))}
    </section>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      {(user: User) => (
        <main className="mx-auto w-full max-w-5xl flex-1 space-y-6 p-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                {user.role === "admin" ? "Platform dashboard" : "Dashboard"}
              </h1>
              <p className="mt-1 text-slate-600 dark:text-slate-400">
                Signed in as {user.email}.
              </p>
            </div>
            <StartButton />
          </div>

          {user.role === "admin" ? <EveryonesDeployments /> : <MyDeployments />}
        </main>
      )}
    </RequireAuth>
  );
}
