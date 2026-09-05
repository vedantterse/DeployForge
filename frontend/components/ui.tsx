/**
 * The shared visual vocabulary.
 *
 * Every surface, button and label in the product comes from here, so that a
 * card on the dashboard and a card in the admin console are the same object
 * rather than two similar ones that drift apart. Components take `className`
 * last so a caller can extend without fighting specificity.
 */

"use client";

import { ReactNode } from "react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/* --- Surfaces ----------------------------------------------------------- */

export function Card({
  children,
  className,
  interactive = false,
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <div
      className={cx(
        "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-sm)]",
        interactive &&
          "transition-[transform,border-color,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-[var(--border-strong)] hover:shadow-[var(--shadow)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  children,
  hint,
  action,
}: {
  children: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{children}</h2>
        {hint && (
          <p className="mt-1 text-sm text-[var(--text-muted)]">{hint}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/* --- Buttons ------------------------------------------------------------ */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--accent)] text-[var(--accent-text)] hover:bg-[var(--accent-hover)] shadow-[var(--shadow-sm)]",
  secondary:
    "bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border-strong)] hover:bg-[var(--surface-3)]",
  ghost:
    "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]",
  danger:
    "bg-[var(--danger-soft)] text-[var(--danger)] border border-[var(--danger)]/40 hover:bg-[var(--danger)] hover:text-white",
};

export function Button({
  children,
  variant = "secondary",
  size = "md",
  loading = false,
  className,
  ...props
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: "sm" | "md";
  loading?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-[var(--radius-sm)] font-medium",
        "transition-colors duration-150",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm",
        BUTTON_STYLES[variant],
        className,
      )}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cx("spin h-3.5 w-3.5", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeWidth="3"
        opacity="0.25"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* --- Labels ------------------------------------------------------------- */

export type Tone = "ok" | "warn" | "danger" | "info" | "neutral" | "accent";

const TONE_STYLES: Record<Tone, string> = {
  ok: "bg-[var(--ok-soft)] text-[var(--ok)] border-[var(--ok)]/30",
  warn: "bg-[var(--warn-soft)] text-[var(--warn)] border-[var(--warn)]/30",
  danger: "bg-[var(--danger-soft)] text-[var(--danger)] border-[var(--danger)]/30",
  info: "bg-[var(--info-soft)] text-[var(--info)] border-[var(--info)]/30",
  accent: "bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--accent)]/30",
  neutral: "bg-[var(--surface-2)] text-[var(--text-muted)] border-[var(--border-strong)]",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        TONE_STYLES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A status dot. `pulse` marks a live app so it reads at a glance. */
export function Dot({ tone = "neutral", pulse = false }: { tone?: Tone; pulse?: boolean }) {
  const colors: Record<Tone, string> = {
    ok: "bg-[var(--ok)]",
    warn: "bg-[var(--warn)]",
    danger: "bg-[var(--danger)]",
    info: "bg-[var(--info)]",
    accent: "bg-[var(--accent)]",
    neutral: "bg-[var(--text-dim)]",
  };
  return (
    <span
      className={cx(
        "inline-block h-2 w-2 shrink-0 rounded-full",
        colors[tone],
        pulse && "live-dot",
      )}
    />
  );
}

/* --- Forms -------------------------------------------------------------- */

export function Input({
  label,
  hint,
  error,
  className,
  ...props
}: {
  label?: string;
  hint?: string;
  error?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1.5 block text-sm font-medium text-[var(--text-muted)]">
          {label}
        </span>
      )}
      <input
        {...props}
        className={cx(
          "w-full rounded-[var(--radius-sm)] border bg-[var(--surface-2)] px-3 py-2 text-sm",
          "placeholder:text-[var(--text-dim)]",
          "transition-colors focus:border-[var(--accent)] focus:outline-none",
          error ? "border-[var(--danger)]" : "border-[var(--border-strong)]",
          className,
        )}
      />
      {error ? (
        <span className="mt-1.5 block text-xs text-[var(--danger)]">{error}</span>
      ) : hint ? (
        <span className="mt-1.5 block text-xs text-[var(--text-dim)]">{hint}</span>
      ) : null}
    </label>
  );
}

/* --- Feedback ----------------------------------------------------------- */

export function Alert({
  tone = "danger",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "rounded-[var(--radius-sm)] border px-4 py-3 text-sm",
        TONE_STYLES[tone],
      )}
      role={tone === "danger" ? "alert" : undefined}
    >
      {title && <p className="mb-1 font-semibold">{title}</p>}
      <div className="opacity-90">{children}</div>
    </div>
  );
}

/**
 * The empty state for a list.
 *
 * Always says what to do next rather than only that there is nothing here —
 * an empty dashboard is the first thing a new student sees.
 */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius)] border border-dashed border-[var(--border-strong)] px-6 py-14 text-center">
      {icon && <div className="mb-4 text-[var(--text-dim)]">{icon}</div>}
      <h3 className="text-base font-semibold">{title}</h3>
      {children && (
        <p className="mt-2 max-w-md text-sm text-[var(--text-muted)]">{children}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cx(
        "shimmer rounded-[var(--radius-sm)] bg-[var(--surface-2)]",
        className,
      )}
    />
  );
}

/* --- Data --------------------------------------------------------------- */

export function Metric({
  label,
  value,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: ReactNode;
  tone?: Tone;
  hint?: string;
}) {
  const valueColor: Record<Tone, string> = {
    ok: "text-[var(--ok)]",
    warn: "text-[var(--warn)]",
    danger: "text-[var(--danger)]",
    info: "text-[var(--info)]",
    accent: "text-[var(--accent)]",
    neutral: "text-[var(--text)]",
  };
  return (
    <Card className="px-4 py-3.5">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-dim)]">
        {label}
      </p>
      <p className={cx("tabular mt-1.5 text-2xl font-semibold", valueColor[tone])}>
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-[var(--text-dim)]">{hint}</p>}
    </Card>
  );
}

/** Monospace text for identifiers: image refs, commit SHAs, container names. */
export function Mono({
  children,
  className,
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <code
      title={title}
      className={cx(
        "font-[family-name:var(--font-geist-mono)] text-xs text-[var(--text-muted)]",
        className,
      )}
    >
      {children}
    </code>
  );
}

/* --- Time --------------------------------------------------------------- */

/**
 * "3 minutes ago" — the only time format this product needs.
 *
 * A student watching a build cares how long ago something happened, not the
 * wall-clock time it happened at.
 */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";

  const seconds = Math.floor((Date.now() - then) / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;

  return new Date(iso).toLocaleDateString();
}

/** "1m 24s" — how long a build took. */
export function duration(from: string | null, to: string | null): string {
  if (!from || !to) return "—";
  const ms = new Date(to).getTime() - new Date(from).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";

  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
