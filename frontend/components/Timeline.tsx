/**
 * A deployment's history, as a vertical timeline.
 *
 * The status badge says where a deployment is; this says how it got there.
 * When a build fails, the stage that failed — download, build, push, start —
 * is the single most useful fact, and it is the one thing a status word cannot
 * carry.
 */

"use client";

import { Dot, Mono, relativeTime, type Tone } from "@/components/ui";
import type { DeploymentEvent } from "@/lib/deployments";

const LEVEL_TONE: Record<DeploymentEvent["level"], Tone> = {
  info: "info",
  success: "ok",
  warning: "warn",
  error: "danger",
};

const STAGE_LABEL: Record<string, string> = {
  download: "Download",
  build: "Build",
  push: "Registry",
  start: "Start",
  stop: "Stop",
  resume: "Resume",
  reconcile: "Reconciled",
};

export default function Timeline({ events }: { events: DeploymentEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-[var(--text-dim)]">
        Nothing has happened to this deployment yet.
      </p>
    );
  }

  return (
    <ol className="relative space-y-0">
      {events.map((event, i) => {
        const tone = LEVEL_TONE[event.level];
        const last = i === events.length - 1;
        return (
          <li key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
            {/* The rail, drawn between dots but not past the last one. */}
            {!last && (
              <span
                aria-hidden
                className="absolute left-[3px] top-4 h-full w-px bg-[var(--border-strong)]"
              />
            )}
            <span className="relative z-10 mt-1.5">
              <Dot tone={tone} />
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="text-sm font-medium">
                  {STAGE_LABEL[event.stage] ?? event.stage}
                </span>
                {event.actor && (
                  <span className="text-xs text-[var(--text-dim)]">
                    by {event.actor}
                  </span>
                )}
                <span className="ml-auto text-xs text-[var(--text-dim)]">
                  {relativeTime(event.created_at)}
                </span>
              </div>
              <p
                className={
                  event.level === "error"
                    ? "mt-0.5 whitespace-pre-wrap break-words text-sm text-[var(--danger)]"
                    : "mt-0.5 whitespace-pre-wrap break-words text-sm text-[var(--text-muted)]"
                }
              >
                {event.message.length > 400 ? (
                  <>
                    {event.message.slice(0, 400)}
                    <Mono className="ml-1">…truncated</Mono>
                  </>
                ) : (
                  event.message
                )}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
