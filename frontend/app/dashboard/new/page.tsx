"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import RepoList from "@/components/RepoList";
import {
  disconnectGitHub,
  getAuthorizeUrl,
  getConnectionStatus,
  type ConnectionStatus,
} from "@/lib/github";

/** The OAuth callback lands here with ?github=connected or ?github=error. */
function readCallbackResult(): { ok: boolean; message: string } | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const outcome = params.get("github");
  if (!outcome) return null;

  window.history.replaceState({}, "", window.location.pathname);

  if (outcome === "connected") {
    return {
      ok: true,
      message: `GitHub account @${params.get("username") ?? ""} connected.`,
    };
  }
  return { ok: false, message: params.get("reason") ?? "Authorization failed." };
}

function NewDeploymentFlow() {
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [callback, setCallback] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    const fromRedirect = readCallbackResult();
    getConnectionStatus()
      .then((s) => {
        if (!active) return;
        setStatus(s);
        if (fromRedirect) setCallback(fromRedirect);
      })
      .catch((err: unknown) => {
        if (active)
          setError(err instanceof Error ? err.message : "Could not load status.");
      });
    return () => {
      active = false;
    };
  }, []);

  /** Forget the stored token so another GitHub account can be connected. */
  async function disconnect() {
    setBusy(true);
    setError(null);
    try {
      await disconnectGitHub();
      setStatus({
        connected: false,
        github_username: null,
        github_user_id: null,
        scopes: null,
        connected_at: null,
      });
      setCallback(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disconnect.");
    } finally {
      setBusy(false);
    }
  }

  async function authorize() {
    setBusy(true);
    setError(null);
    try {
      const { authorize_url } = await getAuthorizeUrl();
      window.location.href = authorize_url; // leaves the app for github.com
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start authorization.");
      setBusy(false);
    }
  }

  const connected = status?.connected === true;

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 p-8">
      <div>
        <Link
          href="/dashboard"
          className="text-sm text-slate-500 underline underline-offset-4 dark:text-slate-400"
        >
          ← Back to dashboard
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">New deployment</h1>
        <p className="mt-1 text-slate-600 dark:text-slate-400">
          Connect GitHub, choose a repository, then choose what inside it to deploy.
        </p>
      </div>

      {/* Step 1 — GitHub */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <span
              className={`mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                connected
                  ? "bg-emerald-500 text-white"
                  : "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200"
              }`}
            >
              {connected ? "✓" : "1"}
            </span>
            <div>
              <h2 className="font-semibold">Connect GitHub</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {status === null
                  ? "Checking…"
                  : connected
                    ? `Connected as @${status.github_username}`
                    : "DeployForge needs read access to list and download your repositories."}
              </p>
            </div>
          </div>

          {connected ? (
            <button
              onClick={() => void disconnect()}
              disabled={busy}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium transition hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              {busy ? "Working…" : "Use a different account"}
            </button>
          ) : (
            <button
              onClick={() => void authorize()}
              disabled={busy || status === null}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              {busy ? "Redirecting…" : "Authorize GitHub"}
            </button>
          )}
        </div>

        {callback && (
          <p
            className={`mt-4 rounded-md px-3 py-2 text-sm ${
              callback.ok
                ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                : "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
            }`}
          >
            {callback.message}
          </p>
        )}

        {error && (
          <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}

        {!connected && status !== null && (
          <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
            The token is exchanged and encrypted on the server — it never reaches
            your browser.
          </p>
        )}
      </section>

      {/* Steps 2 and 3 — repository, then target */}
      {connected ? (
        <RepoList connected />
      ) : (
        <section className="rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Your repositories will appear here once GitHub is connected.
          </p>
        </section>
      )}
    </main>
  );
}

export default function NewDeploymentPage() {
  return <RequireAuth>{() => <NewDeploymentFlow />}</RequireAuth>;
}
