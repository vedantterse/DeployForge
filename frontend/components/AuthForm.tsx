/**
 * The login and signup form.
 *
 * One component for both, because they differ only in which call they make and
 * what the copy says — keeping them together is what stops the two screens
 * drifting apart visually.
 *
 * It also refuses to show itself to someone already signed in: arriving at
 * /login with a valid session sends you straight to your own home rather than
 * asking for a password you have already given.
 */

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, Button, Card, Input, Spinner } from "@/components/ui";
import { ArrowRight, LogoMark } from "@/components/Icons";
import {
  getCurrentUser,
  homeFor,
  login,
  setToken,
  signup,
  type User,
} from "@/lib/auth";

const MIN_PASSWORD_LENGTH = 8;

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // `null` while the stored token is being checked, so the form is not shown
  // and then yanked away from someone who was already signed in.
  const [existing, setExisting] = useState<User | null | undefined>(undefined);

  const isSignup = mode === "signup";

  useEffect(() => {
    let active = true;
    getCurrentUser().then((user) => {
      if (!active) return;
      if (user) {
        setExisting(user);
        router.replace(homeFor(user));
        return;
      }
      setExisting(null);
    });
    return () => {
      active = false;
    };
  }, [router]);

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
      router.push(homeFor(result.user));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-14">
      <div className="mesh" aria-hidden />
      <div className="hairline-grid" aria-hidden />

      <div className="relative z-10 w-full max-w-[26rem]">
        <Link
          href="/"
          className="mb-9 flex items-center justify-center gap-2.5 font-semibold"
        >
          <LogoMark className="h-9 w-9" />
          <span className="text-[17px]">DeployForge</span>
        </Link>

        {existing === undefined ? (
          // Checking the stored session. Same frame as the form, so nothing jumps.
          <Card bezel>
            <div className="flex min-h-[19rem] flex-col items-center justify-center gap-3 p-8">
              <Spinner className="h-5 w-5 text-[var(--text-dim)]" />
              <p className="text-sm text-[var(--text-muted)]">
                Checking your session…
              </p>
            </div>
          </Card>
        ) : existing ? (
          <Card bezel>
            <div className="flex min-h-[19rem] flex-col items-center justify-center gap-3 p-8 text-center">
              <p className="text-sm text-[var(--text-muted)]">
                Already signed in as
              </p>
              <p className="font-medium">{existing.email}</p>
              <p className="text-sm text-[var(--text-dim)]">Taking you through…</p>
            </div>
          </Card>
        ) : (
          <Card bezel className="rise">
            <div className="p-8">
              <h1 className="text-[22px] font-semibold">
                {isSignup ? "Create your account" : "Welcome back"}
              </h1>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-muted)]">
                {isSignup
                  ? "Then connect GitHub and deploy your first repository."
                  : "Sign in to manage your deployments."}
              </p>

              <form onSubmit={submit} className="mt-7 space-y-4">
                <Input
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  autoFocus
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
                    isSignup ? `At least ${MIN_PASSWORD_LENGTH} characters.` : undefined
                  }
                />

                {error && <Alert>{error}</Alert>}

                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  loading={busy}
                  className="w-full"
                  trailing={<ArrowRight className="h-3.5 w-3.5" />}
                >
                  {isSignup ? "Create account" : "Log in"}
                </Button>
              </form>

              <p className="mt-7 text-center text-sm text-[var(--text-muted)]">
                {isSignup ? "Already have an account? " : "New here? "}
                <Link
                  href={isSignup ? "/login" : "/signup"}
                  className="font-medium text-[var(--accent)] underline-offset-4 hover:underline"
                >
                  {isSignup ? "Log in" : "Create one"}
                </Link>
              </p>
            </div>
          </Card>
        )}

        {isSignup && existing === null && (
          <p className="mt-6 text-center text-xs leading-relaxed text-[var(--text-dim)]">
            Signing up creates a standard account. Administrator access is
            granted separately.
          </p>
        )}
      </div>
    </div>
  );
}
