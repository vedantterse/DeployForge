/**
 * Infrastructure: the moving parts every deployment depends on.
 *
 * Its job is to answer one question quickly — "is this student's problem
 * actually my problem?" — so each service says what breaks when it is down,
 * and a degraded service carries the fix rather than just a red dot.
 */

"use client";

import { useCallback, useEffect, useState } from "react";

import RequireAuth from "@/components/RequireAuth";
import {
  Alert,
  Eyebrow,
  Badge,
  Button,
  Card,
  Dot,
  Metric,
  SectionTitle,
  Skeleton,
  cx,
} from "@/components/ui";
import {
  AlertIcon,
  BoxIcon,
  CheckIcon,
  DockerIcon,
  LayersIcon,
  RestartIcon,
  ServerIcon,
} from "@/components/Icons";
import {
  formatSeconds,
  getAnalytics,
  getPlatformStatus,
  type PlatformAnalytics,
  type PlatformStatus,
} from "@/lib/admin";

type ServiceKey = "docker" | "registry" | "router" | "buildpacks";

const SERVICES: {
  key: ServiceKey;
  label: string;
  icon: React.ReactNode;
  does: string;
  breaks: string;
}[] = [
  {
    key: "docker",
    label: "Docker engine",
    icon: <DockerIcon className="h-5 w-5" />,
    does: "Builds every image and runs every container.",
    breaks: "Nothing can be built or started. Running apps stop too.",
  },
  {
    key: "registry",
    label: "Image registry",
    icon: <BoxIcon className="h-5 w-5" />,
    does: "Stores each built image so it is a keepable artifact.",
    breaks: "Builds still work, but images live only on this machine.",
  },
  {
    key: "router",
    label: "Reverse proxy",
    icon: <ServerIcon className="h-5 w-5" />,
    does: "Maps every app's URL to its container.",
    breaks: "Apps keep running but no URL resolves.",
  },
  {
    key: "buildpacks",
    label: "Cloud Native Buildpacks",
    icon: <LayersIcon className="h-5 w-5" />,
    does: "Builds repositories that have no Dockerfile.",
    breaks: "Only Dockerfile and Compose projects can be deployed.",
  },
];

export default function AdminInfrastructurePage() {
  return <RequireAuth adminOnly>{() => <Infrastructure />}</RequireAuth>;
}

function Infrastructure() {
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [data, setData] = useState<PlatformAnalytics | null>(null);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);

  const load = useCallback(async () => {
    setChecking(true);
    try {
      const [s, a] = await Promise.all([getPlatformStatus(), getAnalytics()]);
      setStatus(s);
      setData(a);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check the platform.");
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    // The loader is async: every setState inside it runs after an await, not
    // during this effect. The rule cannot see through the call, so it is
    // silenced here rather than contorting the fetch to satisfy a heuristic.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [load]);

  const degraded = status ? SERVICES.filter((s) => !status[s.key]) : [];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Eyebrow>Services</Eyebrow>
        <h1 className="mt-3 text-[2rem] font-semibold leading-tight">Infrastructure</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Checked live against the running services, not cached.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {status &&
            (degraded.length === 0 ? (
              <Badge tone="ok">
                <CheckIcon className="h-3 w-3" />
                All systems operational
              </Badge>
            ) : (
              <Badge tone="warn">
                <AlertIcon className="h-3 w-3" />
                {degraded.length} degraded
              </Badge>
            ))}
          <Button loading={checking} onClick={load}>
            <RestartIcon className="h-4 w-4" />
            Re-check
          </Button>
        </div>
      </div>

      {error && <Alert>{error}</Alert>}

      {/* --- Services ---------------------------------------------------- */}
      <section>
        <SectionTitle hint="What each service does, and what stops working without it.">
          Services
        </SectionTitle>

        {!status ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {SERVICES.map((service) => {
              const up = status[service.key];
              return (
                <Card
                  key={service.key}
                  className={cx(
                    "p-5",
                    !up && "border-[var(--warn)]/40 bg-[var(--warn-soft)]/20",
                  )}
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={cx(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--r-sm)]",
                        up
                          ? "bg-[var(--ok-soft)] text-[var(--ok)]"
                          : "bg-[var(--warn-soft)] text-[var(--warn)]",
                      )}
                    >
                      {service.icon}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold tracking-tight">
                          {service.label}
                        </h3>
                        <Dot tone={up ? "ok" : "danger"} pulse={up} />
                        <span
                          className={cx(
                            "text-xs font-medium",
                            up ? "text-[var(--ok)]" : "text-[var(--danger)]",
                          )}
                        >
                          {up ? "Operational" : "Unavailable"}
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-[var(--text-muted)]">
                        {service.does}
                      </p>
                      <p className="mt-1.5 text-xs text-[var(--text-dim)]">
                        <span className="font-medium">Without it: </span>
                        {service.breaks}
                      </p>
                      {!up && status.detail[service.key] && (
                        <p className="mt-3 rounded-[var(--r-sm)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--warn)]">
                          {status.detail[service.key]}
                        </p>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* --- Load -------------------------------------------------------- */}
      <section>
        <SectionTitle hint="What this machine is currently carrying.">
          Current load
        </SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Containers running"
            value={data?.running ?? "—"}
            tone={data && data.running > 0 ? "ok" : "neutral"}
            hint="one or more per deployment"
          />
          <Metric
            label="Images stored"
            value={data?.deployments ?? "—"}
            hint="deployments with a build"
          />
          <Metric
            label="Median build"
            value={data ? formatSeconds(data.build_seconds_median) : "—"}
            hint={
              data?.build_seconds_max
                ? `slowest ${formatSeconds(data.build_seconds_max)}`
                : undefined
            }
          />
          <Metric
            label="Suspended"
            value={data?.suspended ?? "—"}
            tone={data && data.suspended > 0 ? "warn" : "neutral"}
            hint="stopped by an administrator"
          />
        </div>
      </section>

      <Card className="p-5">
        <h3 className="font-semibold tracking-tight">How apps are isolated</h3>
        <ul className="mt-3 space-y-2 text-sm text-[var(--text-muted)]">
          {[
            "Each app runs in its own container with capped memory, CPU and process count.",
            "Containers cannot gain privileges and publish no host ports.",
            "A compose stack gets a private network; only its web service is reachable.",
            "Per-account quotas limit how many apps one student can run at once.",
          ].map((line) => (
            <li key={line} className="flex items-start gap-2.5">
              <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--ok)]" />
              {line}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
