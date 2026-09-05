/**
 * One app, as it appears in a list.
 *
 * The card answers, in order: what is it, is it up, where can I open it, and
 * what can I do to it. The live URL is the most valuable thing on the card
 * when an app is running, so it gets the most visual weight there — and is
 * absent entirely when it would 404.
 */

"use client";

import Link from "next/link";
import { useState } from "react";

import StatusBadge from "@/components/StatusBadge";
import { Button, Card, Mono, cx, relativeTime } from "@/components/ui";
import {
  DockerIcon,
  BoxIcon,
  ExternalIcon,
  PlayIcon,
  RestartIcon,
  StopIcon,
  ChevronRight,
} from "@/components/Icons";
import {
  canStart,
  isBusy,
  isRunning,
  restartDeployment,
  startDeployment,
  stopDeployment,
  type Deployment,
} from "@/lib/deployments";

export default function DeploymentCard({
  deployment,
  onChange,
  onError,
  showOwner = false,
  index = 0,
}: {
  deployment: Deployment;
  onChange: (next: Deployment) => void;
  onError: (message: string) => void;
  showOwner?: boolean;
  index?: number;
}) {
  const [pending, setPending] = useState<string | null>(null);

  async function act(
    name: string,
    fn: (id: string) => Promise<Deployment>,
  ) {
    setPending(name);
    onError("");
    try {
      onChange(await fn(deployment.id));
    } catch (err) {
      onError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setPending(null);
    }
  }

  const running = isRunning(deployment.status);
  const busy = isBusy(deployment.status) || pending !== null;
  const isDocker = deployment.build_method === "docker";

  return (
    <Card
      interactive
      className="rise overflow-hidden"
      // Cards resolve in sequence rather than all at once.
      {...({ style: { "--delay": `${Math.min(index, 8) * 45}ms` } } as object)}
    >
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <Link
              href={`/deployments/${deployment.id}`}
              className="truncate font-semibold tracking-tight hover:text-[var(--accent)]"
            >
              {deployment.target_label}
            </Link>
            <StatusBadge status={deployment.status} />
            {deployment.suspended_by_admin && (
              <span className="rounded-full border border-[var(--danger)]/30 bg-[var(--danger-soft)] px-2.5 py-0.5 text-xs font-medium text-[var(--danger)]">
                Suspended
              </span>
            )}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-dim)]">
            {showOwner && deployment.user_email && (
              <span className="text-[var(--text-muted)]">{deployment.user_email}</span>
            )}
            <span className="inline-flex items-center gap-1.5">
              {isDocker ? (
                <DockerIcon className="h-3.5 w-3.5" />
              ) : (
                <BoxIcon className="h-3.5 w-3.5" />
              )}
              {isDocker ? "Dockerfile" : "Buildpack"}
            </span>
            {deployment.detected_framework && (
              <span className="capitalize">{deployment.detected_framework}</span>
            )}
            {deployment.commit_sha && (
              <Mono title={deployment.commit_sha}>
                {deployment.commit_sha.slice(0, 7)}
              </Mono>
            )}
            <span>Updated {relativeTime(deployment.updated_at)}</span>
          </div>

          {/* The URL only appears when it actually resolves. */}
          {running && deployment.url && (
            <a
              href={deployment.url}
              target="_blank"
              rel="noreferrer"
              className="group mt-3 inline-flex items-center gap-2 rounded-[var(--radius-sm)] border border-[var(--ok)]/30 bg-[var(--ok-soft)] px-3 py-1.5 text-sm font-medium text-[var(--ok)] transition-colors hover:bg-[var(--ok)] hover:text-[var(--bg)]"
            >
              {deployment.url.replace(/^https?:\/\//, "")}
              <ExternalIcon className="h-3.5 w-3.5 opacity-70 transition-opacity group-hover:opacity-100" />
            </a>
          )}

          {deployment.status === "failed" && deployment.error_message && (
            <p className="mt-3 line-clamp-2 rounded-[var(--radius-sm)] bg-[var(--danger-soft)] px-3 py-2 text-xs text-[var(--danger)]">
              {deployment.error_message}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {canStart(deployment) && (
            <Button
              size="sm"
              variant="primary"
              loading={pending === "start"}
              disabled={busy}
              onClick={() => act("start", startDeployment)}
            >
              <PlayIcon className="h-3 w-3" />
              Start
            </Button>
          )}
          {running && (
            <>
              <Button
                size="sm"
                loading={pending === "restart"}
                disabled={busy}
                onClick={() => act("restart", restartDeployment)}
                title="Restart"
              >
                <RestartIcon className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                loading={pending === "stop"}
                disabled={busy}
                onClick={() => act("stop", stopDeployment)}
              >
                <StopIcon className="h-3 w-3" />
                Stop
              </Button>
            </>
          )}
          <Link
            href={`/deployments/${deployment.id}`}
            className={cx(
              "inline-flex items-center justify-center rounded-[var(--radius-sm)] p-2",
              "text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
            )}
            title="Details"
          >
            <ChevronRight />
          </Link>
        </div>
      </div>
    </Card>
  );
}
