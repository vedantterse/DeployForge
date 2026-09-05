/**
 * The student's dashboard: everything they have deployed, and its state.
 *
 * Polls while anything is in motion and stops when everything settles, so a
 * page left open on a finished build is not a permanent source of requests.
 */

"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import DeploymentCard from "@/components/DeploymentCard";
import RequireAuth from "@/components/RequireAuth";
import {
  Alert,
  Button,
  EmptyState,
  Metric,
  SectionTitle,
  Skeleton,
} from "@/components/ui";
import { BoxIcon, RocketIcon } from "@/components/Icons";
import {
  isBusy,
  isRunning,
  listDeployments,
  type Deployment,
} from "@/lib/deployments";
import type { User } from "@/lib/auth";

// Fast enough that a build feels live, slow enough to be unnoticeable.
const POLL_MS = 4000;

export default function DashboardPage() {
  return <RequireAuth studentOnly>{(user) => <Dashboard user={user} />}</RequireAuth>;
}

function Dashboard({ user }: { user: User }) {
  const [deployments, setDeployments] = useState<Deployment[] | null>(null);
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const rows = await listDeployments();
      setDeployments(rows);
      return rows;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your apps.");
      return [];
    }
  }, []);

  // Poll only while something is actually moving.
  useEffect(() => {
    let active = true;

    async function tick() {
      const rows = await load();
      if (!active) return;
      if (rows.some((d) => isBusy(d.status))) {
        timer.current = setTimeout(tick, POLL_MS);
      }
    }
    tick();

    return () => {
      active = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [load]);

  function replace(next: Deployment) {
    setDeployments((rows) =>
      rows ? rows.map((d) => (d.id === next.id ? next : d)) : rows,
    );
    // A start or stop settles asynchronously; pick the result up shortly.
    setTimeout(load, 1500);
  }

  const running = deployments?.filter((d) => isRunning(d.status)).length ?? 0;
  const failed = deployments?.filter((d) => d.status === "failed").length ?? 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">My apps</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Everything you have deployed, and whether it is up.
          </p>
        </div>
        {user.can_deploy !== false && (
          <Link href="/dashboard/new">
            <Button variant="primary">
              <RocketIcon className="h-4 w-4" />
              Deploy new app
            </Button>
          </Link>
        )}
      </div>

      {user.can_deploy === false && (
        <Alert tone="warn" title="Deployments are blocked on your account">
          {user.deploy_block_reason ??
            "An administrator has revoked your permission to deploy."}{" "}
          Your existing apps are unaffected and you can still see them here.
        </Alert>
      )}

      {error && <Alert>{error}</Alert>}

      <div className="grid gap-4 sm:grid-cols-3">
        <Metric
          label="Running"
          value={deployments ? running : "—"}
          tone={running > 0 ? "ok" : "neutral"}
          hint={running > 0 ? "serving traffic" : "nothing live right now"}
        />
        <Metric
          label="Total apps"
          value={deployments ? deployments.length : "—"}
        />
        <Metric
          label="Failed"
          value={deployments ? failed : "—"}
          tone={failed > 0 ? "danger" : "neutral"}
          hint={failed > 0 ? "check the build log" : "none"}
        />
      </div>

      <section>
        <SectionTitle hint="Newest first.">Deployments</SectionTitle>

        {deployments === null ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : deployments.length === 0 ? (
          <EmptyState
            icon={<BoxIcon className="h-10 w-10" />}
            title="Nothing deployed yet"
            action={
              <Link href="/dashboard/new">
                <Button variant="primary">
                  <RocketIcon className="h-4 w-4" />
                  Deploy your first app
                </Button>
              </Link>
            }
          >
            Connect your GitHub account, pick a repository, and DeployForge will
            work out how to build it — from a Dockerfile if you have one, with
            buildpacks if you do not.
          </EmptyState>
        ) : (
          <div className="space-y-3">
            {deployments.map((d, i) => (
              <DeploymentCard
                key={d.id}
                deployment={d}
                index={i}
                onChange={replace}
                onError={setError}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
