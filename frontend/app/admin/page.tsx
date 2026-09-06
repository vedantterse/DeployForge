/**
 * The admin overview: the state of the platform in one screen.
 *
 * Ordered by what an administrator needs to know first — is the machine
 * healthy, is anything on fire, what is the class actually doing — rather than
 * by what is easiest to query. Anything that needs acting on is a link to the
 * screen that acts on it.
 */

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import RequireAuth from "@/components/RequireAuth";
import { BarSeries, Breakdown, ChartCard, Gauge } from "@/components/Charts";
import {
  Alert,
  Eyebrow,
  Badge,
  Card,
  Dot,
  Metric,
  SectionTitle,
  Skeleton,
  cx,
} from "@/components/ui";
import {
  AlertIcon,
  BanIcon,
  BoxIcon,
  CheckIcon,
  ChevronRight,
  ServerIcon,
  UsersIcon,
} from "@/components/Icons";
import {
  formatSeconds,
  getAnalytics,
  getPlatformStatus,
  type PlatformAnalytics,
  type PlatformStatus,
} from "@/lib/admin";

export default function AdminOverviewPage() {
  return <RequireAuth adminOnly>{() => <Overview />}</RequireAuth>;
}

function Overview() {
  const [data, setData] = useState<PlatformAnalytics | null>(null);
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await getAnalytics());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load analytics.");
    }
    // Probing real infrastructure is slower; never let it hold up the numbers.
    getPlatformStatus().then(setStatus).catch(() => undefined);
  }, []);

  useEffect(() => {
    // The loader is async: every setState inside it runs after an await, not
    // during this effect. The rule cannot see through the call, so it is
    // silenced here rather than contorting the fetch to satisfy a heuristic.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    const timer = setInterval(load, 20000);
    return () => clearInterval(timer);
  }, [load]);

  const degraded = status
    ? (["docker", "registry", "router", "buildpacks"] as const).filter(
        (k) => !status[k],
      )
    : [];

  return (
    <div className="space-y-8">
      <div>
        <Eyebrow>Platform</Eyebrow>
        <h1 className="mt-3 text-[2rem] font-semibold leading-tight">Platform overview</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          The health of the machine and what everyone on it is running.
        </p>
      </div>

      {error && <Alert>{error}</Alert>}

      {/* --- Things that need attention -------------------------------- */}
      {(degraded.length > 0 || (data?.suspended ?? 0) > 0 || (data?.blocked_users ?? 0) > 0) && (
        <div className="grid gap-3 sm:grid-cols-3">
          {degraded.length > 0 && (
            <AttentionCard
              tone="danger"
              icon={<AlertIcon />}
              title={`${degraded.length} service${degraded.length === 1 ? "" : "s"} degraded`}
              detail={degraded.join(", ")}
              href="/admin/infrastructure"
            />
          )}
          {(data?.suspended ?? 0) > 0 && (
            <AttentionCard
              tone="warn"
              icon={<BanIcon />}
              title={`${data!.suspended} project${data!.suspended === 1 ? "" : "s"} suspended`}
              detail="Stopped by an administrator"
              href="/admin/deployments"
            />
          )}
          {(data?.blocked_users ?? 0) > 0 && (
            <AttentionCard
              tone="warn"
              icon={<UsersIcon />}
              title={`${data!.blocked_users} student${data!.blocked_users === 1 ? "" : "s"} blocked`}
              detail="Deploy permission revoked"
              href="/admin/students"
            />
          )}
        </div>
      )}

      {/* --- Headline numbers ------------------------------------------ */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Students"
          value={data ? data.users - data.admins : "—"}
          hint={data ? `${data.active_users} active accounts` : undefined}
        />
        <Metric
          label="Running now"
          value={data?.running ?? "—"}
          tone={data && data.running > 0 ? "ok" : "neutral"}
          hint={data ? `${data.deployments} deployments total` : undefined}
        />
        <Metric
          label="Failed"
          value={data?.failed ?? "—"}
          tone={data && data.failed > 0 ? "danger" : "neutral"}
          hint="builds that never produced an app"
        />
        <Metric
          label="Median build"
          value={data ? formatSeconds(data.build_seconds_median) : "—"}
          hint={
            data && data.build_seconds_max
              ? `slowest ${formatSeconds(data.build_seconds_max)}`
              : "no builds yet"
          }
        />
      </div>

      {/* --- Charts ----------------------------------------------------- */}
      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          title="Deployment activity"
          hint="New deployments per day, last 14 days"
          className="lg:col-span-2"
        >
          {data ? (
            <BarSeries data={data.daily} label="Deployments per day" />
          ) : (
            <Skeleton className="h-32" />
          )}
        </ChartCard>

        <ChartCard title="Build success" hint="Builds that produced an app">
          {data ? (
            <Gauge
              value={data.success_rate}
              label="Success rate"
              caption={`${data.failed} failed of ${data.deployments}`}
            />
          ) : (
            <Skeleton className="h-40" />
          )}
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard title="How projects are built" hint="Detected build method">
          {data ? (
            <Breakdown
              data={data.by_method}
              empty="Nothing has been built yet."
            />
          ) : (
            <Skeleton className="h-32" />
          )}
        </ChartCard>

        <ChartCard title="Frameworks in use" hint="What students are deploying">
          {data ? (
            <Breakdown
              data={data.by_framework}
              empty="No frameworks detected yet."
            />
          ) : (
            <Skeleton className="h-32" />
          )}
        </ChartCard>

        <ChartCard title="Current state" hint="Every deployment by status">
          {data ? (
            <Breakdown data={data.by_status} empty="No deployments yet." />
          ) : (
            <Skeleton className="h-32" />
          )}
        </ChartCard>
      </div>

      {/* --- Busiest accounts ------------------------------------------- */}
      <section>
        <SectionTitle
          hint="Who is using the most of the shared machine."
          action={
            <Link
              href="/admin/students"
              className="inline-flex items-center gap-1 text-sm text-[var(--accent)] hover:underline"
            >
              All students
              <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          }
        >
          Most active
        </SectionTitle>

        {!data ? (
          <Skeleton className="h-32" />
        ) : data.top_users.length === 0 ? (
          <Card className="p-8 text-center text-sm text-[var(--text-dim)]">
            Nobody has deployed anything yet.
          </Card>
        ) : (
          <Card>
            <ul className="divide-y divide-[var(--hairline)]">
              {data.top_users.map((u) => (
                <li
                  key={u.email}
                  className="flex items-center justify-between gap-4 px-5 py-3"
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <BoxIcon className="h-4 w-4 shrink-0 text-[var(--text-dim)]" />
                    <span className="truncate text-sm">{u.email}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-4 text-xs">
                    {u.running > 0 && (
                      <Badge tone="ok">
                        <Dot tone="ok" pulse />
                        {u.running} running
                      </Badge>
                    )}
                    <span className="tabular text-[var(--text-muted)]">
                      {u.deployments} deployment{u.deployments === 1 ? "" : "s"}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      {/* --- Infrastructure summary ------------------------------------- */}
      <section>
        <SectionTitle
          hint="Checked live. A degraded service explains failures across every account at once."
          action={
            <Link
              href="/admin/infrastructure"
              className="inline-flex items-center gap-1 text-sm text-[var(--accent)] hover:underline"
            >
              Details
              <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          }
        >
          <span className="inline-flex items-center gap-2">
            <ServerIcon />
            Infrastructure
          </span>
        </SectionTitle>

        {!status ? (
          <Skeleton className="h-20" />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(
              [
                ["docker", "Docker", "builds and containers"],
                ["registry", "Registry", "image storage"],
                ["router", "Router", "app URLs"],
                ["buildpacks", "Buildpacks", "repos with no Dockerfile"],
              ] as const
            ).map(([key, label, hint]) => (
              <Card key={key} className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <Dot tone={status[key] ? "ok" : "danger"} pulse={status[key]} />
                  <span className="text-sm font-medium">{label}</span>
                  {status[key] && (
                    <CheckIcon className="ml-auto h-3.5 w-3.5 text-[var(--ok)]" />
                  )}
                </div>
                <p className="mt-0.5 pl-4 text-xs text-[var(--text-dim)]">
                  {status[key] ? hint : "unavailable"}
                </p>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function AttentionCard({
  tone,
  icon,
  title,
  detail,
  href,
}: {
  tone: "danger" | "warn";
  icon: React.ReactNode;
  title: string;
  detail: string;
  href: string;
}) {
  return (
    <Link href={href}>
      <Card
        interactive
        className={cx(
          "flex items-center gap-3 p-4",
          tone === "danger"
            ? "border-[var(--danger)]/40 bg-[var(--danger-soft)]/30"
            : "border-[var(--warn)]/40 bg-[var(--warn-soft)]/30",
        )}
      >
        <span
          className={
            tone === "danger" ? "text-[var(--danger)]" : "text-[var(--warn)]"
          }
        >
          {icon}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{title}</span>
          <span className="block truncate text-xs text-[var(--text-muted)]">
            {detail}
          </span>
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-[var(--text-dim)]" />
      </Card>
    </Link>
  );
}
