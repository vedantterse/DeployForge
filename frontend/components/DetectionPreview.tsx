/**
 * A mock of the app's result panel, used as the hero visual.
 *
 * Static markup, not live data — this is the moment the product exists for, so
 * the landing page shows it rather than describing it.
 */
export default function DetectionPreview() {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--panel)] shadow-2xl shadow-slate-900/10">
      {/* Window chrome */}
      <div className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
        <span className="ml-2 font-mono text-xs text-[var(--muted)]">
          deployforge — new deployment
        </span>
      </div>

      <div className="space-y-4 p-5">
        <div>
          <p className="font-mono text-xs text-[var(--muted)]">Pritesh-30/Amvex</p>
          <p className="mt-1 text-sm font-medium">
            What should DeployForge deploy?
          </p>
        </div>

        {/* Candidate list */}
        <div className="space-y-2">
          {[
            { label: "Whole repository", verdict: "Nothing recognized here", chosen: false, ok: false },
            { label: "frontend/", verdict: "Next.js", method: "buildpack", chosen: true, ok: true },
            { label: "backend/", verdict: "FastAPI", method: "buildpack", chosen: false, ok: true },
          ].map((row) => (
            <div
              key={row.label}
              className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm ${
                row.chosen
                  ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                  : "border-[var(--border)]"
              }`}
            >
              <span
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 ${
                  row.chosen
                    ? "border-[var(--accent)]"
                    : "border-[var(--border)]"
                }`}
              >
                {row.chosen && (
                  <span className="h-2 w-2 rounded-full bg-[var(--accent)]" />
                )}
              </span>
              <span className="font-mono text-xs">{row.label}</span>
              <span
                className={`ml-auto rounded-full px-2 py-0.5 text-xs ${
                  row.ok
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                    : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                }`}
              >
                {row.verdict}
              </span>
              {row.method && (
                <span className="hidden font-mono text-xs text-[var(--muted)] sm:inline">
                  {row.method}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Verdict */}
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950/60">
          <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-100">
            This is a Next.js app in frontend/ — no Docker configuration found.
          </p>
          <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
            {[
              ["Build", "buildpack"],
              ["Commit", "3bb876b"],
              ["Status", "analyzed"],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="uppercase tracking-wide text-[var(--muted)]">{label}</p>
                <p className="mt-0.5 font-mono">{value}</p>
              </div>
            ))}
          </div>
          <p className="mt-3 font-mono text-xs text-[var(--muted)]">
            evidence: package.json, dependency:nextjs
          </p>
        </div>
      </div>
    </div>
  );
}
