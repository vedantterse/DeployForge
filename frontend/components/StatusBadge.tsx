import type { DeploymentStatus } from "@/lib/github";

/** Colour-coded deployment status. Phase 1 only ever produces "analyzed". */
const STYLES: Record<DeploymentStatus, string> = {
  analyzed:
    "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
  queued:
    "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  building:
    "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  built:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  running:
    "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200",
  live:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  failed:
    "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

export default function StatusBadge({ status }: { status: DeploymentStatus }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
        STYLES[status] ?? STYLES.queued
      }`}
    >
      {status}
    </span>
  );
}
