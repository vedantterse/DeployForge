import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";
import { frameworkName, type DeploymentRow } from "@/lib/github";

function formatWhen(iso: string): string {
  const date = new Date(iso);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

/** What was detected, in a few words. */
function detected(row: DeploymentRow): string {
  if (row.detected_type === "docker") return "Docker";
  if (row.detected_type === "framework") return frameworkName(row.detected_framework);
  if (row.detected_type === "unknown") return "Unrecognized";
  return "—";
}

export default function DeploymentTable({
  rows,
  showOwner = false,
  emptyMessage = "No deployments yet.",
}: {
  rows: DeploymentRow[];
  showOwner?: boolean;
  emptyMessage?: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">
        <p className="text-sm text-slate-500 dark:text-slate-400">{emptyMessage}</p>
        <Link
          href="/dashboard/new"
          className="mt-3 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
        >
          Start new deployment
        </Link>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
          <tr>
            {showOwner && <th className="py-2 pr-4">User</th>}
            <th className="py-2 pr-4">Target</th>
            <th className="py-2 pr-4">Detected</th>
            <th className="py-2 pr-4">Build</th>
            <th className="py-2 pr-4">Commit</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2">Date &amp; time</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className="border-t border-slate-100 dark:border-slate-800"
            >
              {showOwner && (
                <td className="py-2.5 pr-4 font-mono text-xs">
                  {row.user_email ?? "—"}
                </td>
              )}
              <td className="py-2.5 pr-4">
                <span className="font-mono">{row.full_name}</span>
                {row.deploy_path && (
                  <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs dark:bg-slate-800">
                    {row.deploy_path}/
                  </span>
                )}
              </td>
              <td className="py-2.5 pr-4">{detected(row)}</td>
              <td className="py-2.5 pr-4 font-mono text-xs">
                {row.build_method ?? "—"}
              </td>
              <td className="py-2.5 pr-4 font-mono text-xs">
                {row.commit_sha ? row.commit_sha.slice(0, 7) : "—"}
              </td>
              <td className="py-2.5 pr-4">
                <StatusBadge status={row.status} />
              </td>
              <td className="py-2.5 whitespace-nowrap text-slate-600 dark:text-slate-400">
                {formatWhen(row.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
