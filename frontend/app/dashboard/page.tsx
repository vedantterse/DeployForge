/**
 * The student's dashboard: the apps they own, and the state of each.
 *
 * An app is a repository target they connected; a deployment is one attempt to
 * build and run it. This lists apps — rebuilding an app does not give them a
 * second one, and the builds live inside the app that owns them.
 *
 * Polls while anything is in motion and stops when everything settles, so a
 * page left open on a finished build is not a permanent source of requests.
 */

"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import AppCard from "@/components/AppCard";
import RequireAuth from "@/components/RequireAuth";
import {
  Alert,
  Button,
  EmptyState,
  Eyebrow,
  Metric,
  SectionTitle,
  Skeleton,
} from "@/components/ui";
import {
  AlertIcon,
  ArrowRight,
  BoxIcon,
  RocketIcon,
  ServerIcon,
} from "@/components/Icons";
import { appIsBusy, listApps, type App } from "@/lib/apps";
import { isRunning } from "@/lib/deployments";
import type { User } from "@/lib/auth";

// Fast enough that a build feels live, slow enough to be unnoticeable.
const POLL_MS = 4000;

export default function DashboardPage() {
  return <RequireAuth studentOnly>{(user) => <Dashboard user={user} />}</RequireAuth>;
}

function Dashboard({ user }: { user: User }) {
  const [apps, setApps] = useState<App[] | null>(null);
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const rows = await listApps();
      setApps(rows);
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
      if (rows.some(appIsBusy)) {
        timer.current = setTimeout(tick, POLL_MS);
      }
    }
    tick();

    return () => {
      active = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [load]);

  // A start or stop settles asynchronously and changes the app's current
  // deployment, so the app is re-read rather than patched in place.
  function refresh() {
    setTimeout(load, 1500);
  }

  const running =
    apps?.filter((a) => a.current && isRunning(a.current.status)).length ?? 0;
  const failed =
    apps?.filter((a) => a.current?.status === "failed").length ?? 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>Your workspace</Eyebrow>
          <h1 className="mt-3 text-[2rem] font-semibold leading-tight">My apps</h1>
          <p className="mt-1.5 text-sm text-[var(--text-muted)]">
            Everything you have deployed, and whether it is up.
          </p>
        </div>
        {user.can_deploy !== false && (
          <Link href="/dashboard/new">
            <Button
              variant="primary"
              trailing={<ArrowRight className="h-3 w-3" />}
            >
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
          value={apps ? running : "—"}
          tone={running > 0 ? "ok" : "neutral"}
          hint={running > 0 ? "serving traffic" : "nothing live right now"}
          icon={<ServerIcon className="h-4 w-4" />}
        />
        <Metric
          label="Total apps"
          value={apps ? apps.length : "—"}
          icon={<BoxIcon className="h-4 w-4" />}
        />
        <Metric
          label="Failed"
          value={apps ? failed : "—"}
          tone={failed > 0 ? "danger" : "neutral"}
          hint={failed > 0 ? "check the build log" : "none"}
          icon={<AlertIcon className="h-4 w-4" />}
        />
      </div>

      <section>
        <SectionTitle hint="Most recently connected first.">Apps</SectionTitle>

        {apps === null ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : apps.length === 0 ? (
          <EmptyState
            icon={<BoxIcon className="h-10 w-10" />}
            title="Nothing deployed yet"
            action={
              <Link href="/dashboard/new">
                <Button
                  variant="primary"
                  size="lg"
                  trailing={<ArrowRight className="h-3.5 w-3.5" />}
                >
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
            {apps.map((app, i) => (
              <AppCard
                key={app.id}
                app={app}
                index={i}
                onChange={refresh}
                onError={setError}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
