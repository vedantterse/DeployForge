/**
 * One app, as it appears in a list.
 *
 * The card answers, in order: what is it, is it up, where can I open it, and
 * what can I do to it. The live URL is the most valuable thing on the card
 * when an app is running, so it carries the most weight there — and is absent
 * entirely when it would 404.
 *
 * Only the name navigates. The card is not a giant link, because it also holds
 * buttons and an external URL, and nesting those inside a link makes every
 * click ambiguous.
 */

"use client";

import Link from "next/link";
import { useState } from "react";

import StatusBadge from "@/components/StatusBadge";
import { Badge, Button, Card, Mono, cx, relativeTime } from "@/components/ui";
import {
  BoxIcon,
  ChevronRight,
  DockerIcon,
  ExternalIcon,
  LayersIcon,
  PlayIcon,
  RestartIcon,
  StopIcon,
} from "@/components/Icons";
import {
  canStart,
  isBusy,
  isRunning,
  methodMeta,
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

  async function act(name: string, fn: (id: string) => Promise<Deployment>) {
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
  const isCompose = deployment.build_method === "compose";
  const method = methodMeta(deployment);

  return (
    <Card
      interactive
      className="rise overflow-hidden"
      // Cards resolve in sequence rather than all at once.
      {...({
        style: { "--delay": `${Math.min(index, 8) * 55}ms` },
      } as object)}
    >
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <Link
              href={`/deployments/${deployment.id}`}
              className="truncate font-semibold underline-offset-[5px] decoration-[var(--accent-line)] transition-colors duration-[var(--t-hover)] hover:text-[var(--accent)] hover:underline"
              title="Open this deployment"
            >
              {deployment.target_label}
            </Link>
            <StatusBadge status={deployment.status} />
            {deployment.suspended_by_admin && (
              <Badge tone="danger">Suspended</Badge>
            )}
          </div>

          <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-[var(--text-dim)]">
            {showOwner && deployment.user_email && (
              <span className="text-[var(--text-muted)]">{deployment.user_email}</span>
            )}
            <span className="inline-flex items-center gap-1.5">
              {isCompose ? (
                <LayersIcon className="h-3.5 w-3.5" />
              ) : isDocker ? (
                <DockerIcon className="h-3.5 w-3.5" />
              ) : (
                <BoxIcon className="h-3.5 w-3.5" />
              )}
              {method.label}
            </span>
            {isCompose && deployment.compose_services && (
              <span>{deployment.compose_services.length} services</span>
            )}
            {!isCompose && deployment.detected_framework && (
              <span className="capitalize">{deployment.detected_framework}</span>
            )}
            {deployment.commit_sha && (
              <Mono title={deployment.commit_sha}>
                {deployment.commit_sha.slice(0, 7)}
              </Mono>
            )}
            <span>Updated {relativeTime(deployment.updated_at)}</span>
          </div>

          {/* The URL appears only while it actually resolves. */}
          {running && deployment.url && (
            <a
              href={deployment.url}
              target="_blank"
              rel="noreferrer"
              className={cx(
                "group/url mt-3.5 inline-flex items-center gap-2 rounded-full border border-[var(--ok)]/25 bg-[var(--ok-soft)]",
                "px-3.5 py-1.5 font-[family-name:var(--font-jetbrains-mono)] text-xs font-medium text-[var(--ok)]",
                "transition-colors duration-[var(--t-hover)] ease-[var(--ease-out)] hover:bg-[var(--ok)] hover:text-[var(--bg-deep)]",
              )}
            >
              {deployment.url.replace(/^https?:\/\//, "")}
              <ExternalIcon className="h-3 w-3 opacity-60 transition-opacity group-hover/url:opacity-100" />
            </a>
          )}

          {deployment.status === "failed" && deployment.error_message && (
            <p className="mt-3.5 line-clamp-2 rounded-[var(--r-sm)] border border-[var(--danger)]/20 bg-[var(--danger-soft)] px-3.5 py-2.5 text-xs leading-relaxed text-[var(--danger)]">
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
                aria-label="Restart"
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
            aria-label={`Open ${deployment.target_label}`}
            className={cx(
              "group/go flex h-9 w-9 items-center justify-center rounded-full border border-[var(--hairline)]",
              "text-[var(--text-dim)] transition-[color,background-color,transform] duration-[var(--t-hover)] ease-[var(--ease-spring)]",
              "hover:translate-x-0.5 hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
            )}
            title="Details"
          >
            <ChevronRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </Card>
  );
}
