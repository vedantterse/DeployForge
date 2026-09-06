/**
 * The shared visual vocabulary.
 *
 * Every surface, control and label comes from here, so a card on the student
 * dashboard and a card in the admin console are the same object rather than
 * two similar ones that drift apart. Components take `className` last so a
 * caller can extend without fighting specificity.
 */

"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/* --- Surfaces ----------------------------------------------------------- */

/**
 * A panel.
 *
 * `bezel` wraps it in an outer tray with a hairline and concentric radii — the
 * machined-hardware look, reserved for a page's most important object. Ordinary
 * panels stay flat, because bezelling everything makes nothing stand out.
 */
export function Card({
  children,
  className,
  interactive = false,
  bezel = false,
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  bezel?: boolean;
}) {
  const panel = (
    <div
      className={cx(
        "plate",
        interactive &&
          "transition-[transform,border-color,box-shadow] duration-[var(--t-hover)] ease-[var(--ease-out)] hover:-translate-y-[3px] hover:border-[var(--hairline-strong)] hover:shadow-[var(--shadow)]",
        className,
      )}
    >
      {children}
    </div>
  );

  return bezel ? <div className="bezel">{panel}</div> : panel;
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
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold">{children}</h2>
        {hint && (
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-[var(--text-muted)]">
            {hint}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}

/** A small uppercase pill above a heading. Sets the section before it starts. */
export function Eyebrow({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-2 rounded-full border border-[var(--hairline)] bg-[var(--surface)] px-3 py-1",
        "text-[10px] font-medium uppercase tracking-[0.18em] text-[var(--text-muted)]",
        className,
      )}
    >
      {children}
    </span>
  );
}

/* --- Buttons ------------------------------------------------------------ */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  // Warm white on black. The most emphatic thing available without adding
  // another colour to compete with the four status hues.
  primary:
    "bg-[var(--solid)] text-[var(--solid-text)] shadow-[var(--shadow-sm)] hover:brightness-105",
  secondary:
    "bg-[var(--surface-2)] text-[var(--text)] border border-[var(--hairline-strong)] hover:bg-[var(--surface-3)] hover:border-[var(--hairline-strong)]",
  ghost: "text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)]",
  danger:
    "bg-[var(--danger-soft)] text-[var(--danger)] border border-[var(--danger)]/30 hover:bg-[var(--danger)] hover:text-[var(--bg-deep)]",
};

/**
 * A button.
 *
 * Pill-shaped, and it acknowledges a press by scaling down — the cheapest way
 * to make a control feel physical. `trailing` nests an icon in its own circular
 * well flush with the right padding, which drifts diagonally on hover.
 */
export function Button({
  children,
  variant = "secondary",
  size = "md",
  loading = false,
  trailing,
  className,
  ...props
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  trailing?: ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={cx(
        "group inline-flex items-center justify-center gap-2 rounded-full font-medium",
        "transition-[background-color,color,transform,filter,border-color] duration-[var(--t-hover)] ease-[var(--ease-out)]",
        "active:scale-[0.97] active:duration-[var(--t-press)]",
        "disabled:pointer-events-none disabled:opacity-45",
        size === "sm" && "px-3.5 py-1.5 text-xs",
        size === "md" && "px-4 py-2 text-sm",
        size === "lg" && "px-6 py-3 text-[15px]",
        // A trailing icon sits in its own well flush with the edge, so the
        // right padding shrinks to meet it.
        Boolean(trailing) && "pr-1.5",
        BUTTON_STYLES[variant],
        className,
      )}
    >
      {loading && <Spinner />}
      {children}
      {trailing && (
        <span
          className={cx(
            "flex items-center justify-center rounded-full",
            "bg-[oklch(0%_0_0/0.12)] transition-transform duration-[var(--t-hover)] ease-[var(--ease-spring)]",
            "group-hover:translate-x-0.5 group-hover:-translate-y-px group-hover:scale-105",
            size === "lg" ? "h-8 w-8" : "h-6 w-6",
            variant !== "primary" && "bg-[oklch(100%_0_0/0.08)]",
          )}
        >
          {trailing}
        </span>
      )}
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
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
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
  ok: "bg-[var(--ok-soft)] text-[var(--ok)] border-[var(--ok)]/25",
  warn: "bg-[var(--warn-soft)] text-[var(--warn)] border-[var(--warn)]/25",
  danger: "bg-[var(--danger-soft)] text-[var(--danger)] border-[var(--danger)]/25",
  info: "bg-[var(--info-soft)] text-[var(--info)] border-[var(--info)]/25",
  accent: "bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--accent-line)]",
  neutral: "bg-[var(--surface-2)] text-[var(--text-muted)] border-[var(--hairline)]",
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

/** A status dot. `pulse` marks a live app so it reads across a long list. */
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
        "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
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
        <span className="mb-2 block text-xs font-medium uppercase tracking-wider text-[var(--text-dim)]">
          {label}
        </span>
      )}
      <input
        {...props}
        className={cx(
          "w-full rounded-[var(--r-sm)] border bg-[var(--surface-2)] px-3.5 py-2.5 text-sm",
          "placeholder:text-[var(--text-dim)] shadow-[var(--bevel)]",
          "transition-[border-color,background-color] duration-[var(--t-hover)] ease-[var(--ease-out)]",
          "focus:border-[var(--accent-line)] focus:bg-[var(--surface-3)] focus:outline-none",
          error ? "border-[var(--danger)]/60" : "border-[var(--hairline-strong)]",
          className,
        )}
      />
      {error ? (
        <span className="mt-2 block text-xs text-[var(--danger)]">{error}</span>
      ) : hint ? (
        <span className="mt-2 block text-xs text-[var(--text-dim)]">{hint}</span>
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
        "rounded-[var(--r-sm)] border px-4 py-3 text-sm leading-relaxed",
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
 * Always says what to do next rather than only that there is nothing here — an
 * empty dashboard is the first thing a new student sees.
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
    <div className="flex flex-col items-center justify-center rounded-[var(--r-lg)] border border-dashed border-[var(--hairline-strong)] px-6 py-20 text-center">
      {icon && (
        <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-full border border-[var(--hairline)] bg-[var(--surface)] text-[var(--text-dim)]">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold">{title}</h3>
      {children && (
        <p className="mt-2 max-w-md text-sm leading-relaxed text-[var(--text-muted)]">
          {children}
        </p>
      )}
      {action && <div className="mt-7">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cx("shimmer rounded-[var(--r-sm)] bg-[var(--surface-2)]", className)}
    />
  );
}

/* --- Data --------------------------------------------------------------- */

export function Metric({
  label,
  value,
  tone = "neutral",
  hint,
  icon,
}: {
  label: string;
  value: ReactNode;
  tone?: Tone;
  hint?: string;
  icon?: ReactNode;
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
    <Card className="px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--text-dim)]">
          {label}
        </p>
        {icon && <span className="text-[var(--text-dim)]">{icon}</span>}
      </div>
      <p className={cx("tabular mt-2 text-[28px] font-semibold leading-none", valueColor[tone])}>
        {value}
      </p>
      {hint && <p className="mt-2 text-xs text-[var(--text-dim)]">{hint}</p>}
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
        "font-[family-name:var(--font-jetbrains-mono)] text-xs text-[var(--text-muted)]",
        className,
      )}
    >
      {children}
    </code>
  );
}

/* --- Scroll reveal ------------------------------------------------------ */

/**
 * Reveal children once they enter the viewport.
 *
 * An IntersectionObserver, never a scroll listener: a listener fires on every
 * frame and reflows with it, which is felt immediately on a phone.
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    // No observer (an old browser, or a test runner): reveal on the next
    // frame rather than synchronously, so the effect only schedules work.
    if (typeof IntersectionObserver === "undefined") {
      const frame = requestAnimationFrame(() => setShown(true));
      return () => cancelAnimationFrame(frame);
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          observer.disconnect(); // reveal once, then stop watching
        }
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.05 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={cx("reveal", shown && "shown", className)}
      style={{ "--delay": `${delay}ms` } as React.CSSProperties}
    >
      {children}
    </div>
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
