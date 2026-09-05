/**
 * The login and signup form.
 *
 * One component for both, because they differ only in which call they make and
 * what the copy says — and keeping them together means the two screens cannot
 * drift apart visually.
 */

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert, Button, Card, Input } from "@/components/ui";
import { LogoMark } from "@/components/Icons";
import { login, setToken, signup } from "@/lib/auth";

const MIN_PASSWORD_LENGTH = 8;

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");

    if (isSignup && password.length < MIN_PASSWORD_LENGTH) {
      setError(`Choose a password of at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }

    setBusy(true);
    try {
      const result = isSignup
        ? await signup(email, password)
        : await login(email, password);
      setToken(result.access_token);
      // Each role has its own home. An administrator runs the platform and has
      // no apps of their own, so the student dashboard is not their landing
      // page — it is a screen they never see.
      router.push(result.user.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-12">
      <div className="aurora" aria-hidden />
      <div className="grid-backdrop" aria-hidden />

      <div className="relative z-10 w-full max-w-md">
        <Link
          href="/"
          className="mb-8 flex items-center justify-center gap-2.5 font-semibold tracking-tight"
        >
          <LogoMark className="h-9 w-9" />
          <span className="text-lg">DeployForge</span>
        </Link>

        <Card className="p-7 shadow-[var(--shadow-lg)]">
          <h1 className="text-xl font-semibold tracking-tight">
            {isSignup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-1.5 text-sm text-[var(--text-muted)]">
            {isSignup
              ? "Then connect GitHub and deploy your first repository."
              : "Sign in to manage your deployments."}
          </p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="you@college.edu"
            />
            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={isSignup ? "new-password" : "current-password"}
              placeholder="••••••••"
              hint={
                isSignup
                  ? `At least ${MIN_PASSWORD_LENGTH} characters.`
                  : undefined
              }
            />

            {error && <Alert>{error}</Alert>}

            <Button
              type="submit"
              variant="primary"
              loading={busy}
              className="w-full"
            >
              {isSignup ? "Create account" : "Log in"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-[var(--text-muted)]">
            {isSignup ? "Already have an account? " : "New here? "}
            <Link
              href={isSignup ? "/login" : "/signup"}
              className="font-medium text-[var(--accent)] hover:underline"
            >
              {isSignup ? "Log in" : "Create one"}
            </Link>
          </p>
        </Card>

        {isSignup && (
          <p className="mt-5 text-center text-xs text-[var(--text-dim)]">
            Signing up creates a standard account. Administrator access is
            granted separately.
          </p>
        )}
      </div>
    </div>
  );
}
