"use client";

import { Badge, Dot, Spinner, type Tone } from "@/components/ui";
import { statusMeta, type DeploymentStatus } from "@/lib/deployments";

/**
 * A deployment's status, as one consistent object.
 *
 * The dot pulses only when the app is actually serving traffic, and a spinner
 * replaces it while something is in flight — so "working" and "working on it"
 * never look the same.
 */
export default function StatusBadge({
  status,
  className,
}: {
  status: DeploymentStatus;
  className?: string;
}) {
  const { label, tone, moving } = statusMeta(status);
  const running = status === "running" || status === "live";

  return (
    <Badge tone={tone as Tone} className={className}>
      {moving ? <Spinner className="h-3 w-3" /> : <Dot tone={tone as Tone} pulse={running} />}
      {label}
    </Badge>
  );
}
