"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { setToken, login, signup } from "@/lib/auth";

/** Shared email/password form for the login and signup pages. */
export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = isSignup
        ? await signup(email, password)
        : await login(email, password);
      setToken(res.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="w-full max-w-sm space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-6 shadow-xl shadow-slate-900/5"
    >
      <div>
        <h1 className="text-2xl font-bold">
          {isSignup ? "Create an account" : "Log in"}
        </h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {isSignup
            ? "New accounts start with the user role."
            : "Welcome back to DeployForge."}
        </p>
      </div>

      <label className="block">
        <span className="text-sm font-medium">Email</span>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none transition focus:border-[var(--accent)]"
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium">Password</span>
        <input
          type="password"
          required
          minLength={isSignup ? 8 : 1}
          maxLength={72}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={isSignup ? "new-password" : "current-password"}
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm outline-none transition focus:border-[var(--accent)]"
        />
        {isSignup && (
          <span className="mt-1 block text-xs text-[var(--muted)]">
            8–72 characters.
          </span>
        )}
      </label>

      {error && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:brightness-110 disabled:opacity-50"
      >
        {busy ? "Please wait…" : isSignup ? "Sign up" : "Log in"}
      </button>

      <p className="text-center text-sm text-[var(--muted)]">
        {isSignup ? "Already have an account? " : "No account yet? "}
        <Link
          href={isSignup ? "/login" : "/signup"}
          className="font-medium underline underline-offset-4"
        >
          {isSignup ? "Log in" : "Sign up"}
        </Link>
      </p>
    </form>
  );
}
