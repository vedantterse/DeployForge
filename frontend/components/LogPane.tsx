/**
 * A log viewer for build and runtime output.
 *
 * Follows the tail while new lines arrive, but stops the moment the reader
 * scrolls up — nothing is more frustrating than a log that yanks you back to
 * the bottom while you are reading the error halfway up it.
 */

"use client";

import { useEffect, useRef, useState } from "react";

import { Button, Spinner, cx } from "@/components/ui";

export default function LogPane({
  text,
  loading = false,
  streaming = false,
  empty = "Nothing logged yet.",
  className,
}: {
  text: string;
  loading?: boolean;
  streaming?: boolean;
  empty?: string;
  className?: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);

  // Re-pin to the bottom whenever new output arrives, unless the reader has
  // scrolled away from it.
  useEffect(() => {
    if (!follow || !box.current) return;
    box.current.scrollTop = box.current.scrollHeight;
  }, [text, follow]);

  function onScroll() {
    const el = box.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setFollow(atBottom);
  }

  return (
    <div className={cx("relative", className)}>
      <div
        ref={box}
        onScroll={onScroll}
        className="log-pane h-[26rem] overflow-auto rounded-[var(--radius-sm)] border border-[var(--border)] bg-[oklch(12%_0.015_265)] p-4 text-[var(--text-muted)]"
      >
        {loading && !text ? (
          <span className="flex items-center gap-2 text-[var(--text-dim)]">
            <Spinner /> Loading…
          </span>
        ) : text ? (
          text
        ) : (
          <span className="text-[var(--text-dim)]">{empty}</span>
        )}
      </div>

      {streaming && (
        <span className="pointer-events-none absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-[var(--info-soft)] px-2.5 py-1 text-xs font-medium text-[var(--info)]">
          <Spinner className="h-3 w-3" />
          Live
        </span>
      )}

      {!follow && (
        <Button
          size="sm"
          className="absolute bottom-3 right-3"
          onClick={() => {
            setFollow(true);
            if (box.current) box.current.scrollTop = box.current.scrollHeight;
          }}
        >
          Jump to latest
        </Button>
      )}
    </div>
  );
}
