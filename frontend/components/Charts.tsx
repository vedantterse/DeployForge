/**
 * Small inline charts for the admin overview.
 *
 * Hand-drawn SVG rather than a charting library: there are three shapes, they
 * need to inherit the theme's tokens, and a 90 KB dependency to draw fourteen
 * rectangles would be a poor trade. Each one degrades to a readable empty
 * state, because an admin opening a fresh platform sees no data at all.
 */

"use client";

import { ReactNode } from "react";

import { Card, cx } from "@/components/ui";

/* --- Bars over time ----------------------------------------------------- */

/**
 * Fill in the days that have no deployments.
 *
 * The API only returns days something happened on. Plotting those alone would
 * stretch a single busy day across the whole chart and imply a fortnight of
 * activity, so the missing days are added back as zeroes and the axis means
 * what it says.
 */
function overDays(
  data: { date: string; count: number }[],
  days: number,
): { date: string; count: number }[] {
  const counts = new Map(data.map((d) => [d.date, d.count]));
  const series: { date: string; count: number }[] = [];

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  for (let i = days - 1; i >= 0; i--) {
    const day = new Date(today);
    day.setDate(today.getDate() - i);
    // Local calendar date, matching the dates the API returns.
    const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
    series.push({ date: key, count: counts.get(key) ?? 0 });
  }
  return series;
}

export function BarSeries({
  data,
  label,
  days = 14,
}: {
  data: { date: string; count: number }[];
  label: string;
  days?: number;
}) {
  if (data.length === 0) {
    return (
      <p className="flex h-32 items-center justify-center text-sm text-[var(--text-dim)]">
        No deployments yet.
      </p>
    );
  }

  const series = overDays(data, days);
  const max = Math.max(...series.map((d) => d.count), 1);

  return (
    <div>
      <div className="flex h-32 items-end gap-1.5" role="img" aria-label={label}>
        {series.map((point) => {
          const height = Math.max((point.count / max) * 100, 4);
          return (
            <div
              key={point.date}
              // `h-full` matters: the bar's height is a percentage, and a
              // percentage of an auto-height parent is zero — the chart would
              // render as an empty strip.
              className="group relative flex h-full flex-1 items-end"
              title={`${point.date}: ${point.count}`}
            >
              <div
                className={cx(
                  "w-full rounded-t-sm transition-opacity group-hover:opacity-80",
                  point.count > 0
                    ? "bg-[var(--accent)]"
                    : "bg-[var(--surface-3)]",
                )}
                style={{ height: `${height}%` }}
              />
              {/* The exact value on hover, so the axis can stay off. */}
              <span className="pointer-events-none absolute -top-6 left-1/2 hidden -translate-x-1/2 rounded bg-[var(--surface-3)] px-1.5 py-0.5 text-[11px] text-[var(--text)] group-hover:block">
                {point.count}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-[var(--text-dim)]">
        <span>{formatDay(series[0].date)}</span>
        <span>{formatDay(series[series.length - 1].date)}</span>
      </div>
    </div>
  );
}

function formatDay(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/* --- Proportional breakdown --------------------------------------------- */

const SERIES_COLORS = [
  "var(--accent)",
  "var(--info)",
  "var(--ok)",
  "var(--warn)",
  "var(--danger)",
  "var(--text-dim)",
];

export function Breakdown({
  data,
  empty = "Nothing recorded yet.",
}: {
  data: Record<string, number>;
  empty?: string;
}) {
  const entries = Object.entries(data)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, n]) => sum + n, 0);

  if (total === 0) {
    return <p className="py-6 text-center text-sm text-[var(--text-dim)]">{empty}</p>;
  }

  return (
    <div>
      {/* One stacked bar, so proportion is visible before any label is read. */}
      <div className="flex h-2.5 overflow-hidden rounded-full bg-[var(--surface-3)]">
        {entries.map(([key, n], i) => (
          <div
            key={key}
            style={{
              width: `${(n / total) * 100}%`,
              background: SERIES_COLORS[i % SERIES_COLORS.length],
            }}
            title={`${key}: ${n}`}
          />
        ))}
      </div>
      <ul className="mt-3 space-y-1.5">
        {entries.map(([key, n], i) => (
          <li key={key} className="flex items-center gap-2 text-sm">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }}
            />
            <span className="flex-1 truncate capitalize text-[var(--text-muted)]">
              {key}
            </span>
            <span className="tabular font-medium">{n}</span>
            <span className="tabular w-10 text-right text-xs text-[var(--text-dim)]">
              {Math.round((n / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* --- Ratio dial --------------------------------------------------------- */

export function Gauge({
  value,
  label,
  caption,
}: {
  /** 0–1. */
  value: number | null;
  label: string;
  caption?: string;
}) {
  const pct = value === null ? 0 : Math.max(0, Math.min(1, value));
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const tone =
    value === null
      ? "var(--text-dim)"
      : pct >= 0.8
        ? "var(--ok)"
        : pct >= 0.5
          ? "var(--warn)"
          : "var(--danger)";

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 100 100" className="h-28 w-28 -rotate-90">
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth="9"
        />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke={tone}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - pct)}
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <p className="tabular -mt-[4.6rem] text-2xl font-semibold">
        {value === null ? "—" : `${Math.round(pct * 100)}%`}
      </p>
      <p className="mt-11 text-sm font-medium">{label}</p>
      {caption && (
        <p className="mt-0.5 text-xs text-[var(--text-dim)]">{caption}</p>
      )}
    </div>
  );
}

/* --- Panel -------------------------------------------------------------- */

export function ChartCard({
  title,
  hint,
  children,
  className,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cx("p-5", className)}>
      <div className="mb-4">
        <h3 className="font-semibold tracking-tight">{title}</h3>
        {hint && <p className="mt-0.5 text-xs text-[var(--text-dim)]">{hint}</p>}
      </div>
      {children}
    </Card>
  );
}
