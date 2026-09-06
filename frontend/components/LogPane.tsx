/**
 * A log viewer for build and runtime output.
 *
 * Follows the tail while new lines arrive, and stops the moment the reader
 * scrolls up — nothing is more frustrating than a log that yanks you back to
 * the bottom while you are reading the error halfway up it.
 */

"use client";

import { useEffect, useRef, useState } from "react";

import { Button, Spinner, cx } from "@/components/ui";
import { ArrowRight } from "@/components/Icons";

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
      {/* A terminal reads as a physical object: an outer tray holding a
          recessed, darker well. */}
      <div className="bezel">
        <div className="overflow-hidden bg-[var(--bg-deep)] shadow-[inset_0_1px_0_oklch(100%_0_0/0.04)]">
          <div className="flex items-center justify-between gap-3 border-b border-[var(--hairline)] px-4 py-2.5">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[var(--danger)]/50" />
              <span className="h-2 w-2 rounded-full bg-[var(--warn)]/50" />
              <span className="h-2 w-2 rounded-full bg-[var(--ok)]/50" />
            </div>
            {streaming && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--info)]/25 bg-[var(--info-soft)] px-2.5 py-0.5 text-[11px] font-medium text-[var(--info)]">
                <Spinner className="h-2.5 w-2.5" />
                Live
              </span>
            )}
          </div>

          <div
            ref={box}
            onScroll={onScroll}
            className="log-pane h-[26rem] overflow-auto px-4 py-3.5 text-[var(--text-muted)]"
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
        </div>
      </div>

      {!follow && (
        <Button
          size="sm"
          variant="primary"
          className="absolute bottom-5 right-5 shadow-[var(--shadow)]"
          trailing={<ArrowRight className="h-3 w-3 rotate-90" />}
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
