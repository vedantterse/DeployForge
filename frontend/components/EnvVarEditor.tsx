"use client";

import { useEffect, useState } from "react";
import {
  listEnvVars,
  saveEnvVars,
  type EnvVar,
  type EnvVarInput,
} from "@/lib/github";

/**
 * One editable row.
 *
 * `stored` marks a variable that already exists on the server. For a stored
 * secret the value box starts empty with a placeholder — the plaintext was
 * never sent to the browser — and leaving it empty sends null on save, which
 * the API reads as "keep what you have".
 */
type Row = {
  key: string;
  value: string;
  is_secret: boolean;
  stored: boolean;
  storedSecret: boolean;
};

function toRow(variable: EnvVar): Row {
  return {
    key: variable.key,
    value: variable.value ?? "",
    is_secret: variable.is_secret,
    stored: true,
    storedSecret: variable.is_secret,
  };
}

const BLANK: Row = {
  key: "",
  value: "",
  is_secret: false,
  stored: false,
  storedSecret: false,
};

/** Parse pasted `KEY=value` lines, so a .env file can be dropped in at once. */
function parseDotEnv(text: string): Row[] {
  const rows: Row[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    const key = line.slice(0, index).trim().replace(/^export\s+/, "");
    let value = line.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (key) rows.push({ ...BLANK, key, value });
  }
  return rows;
}

export default function EnvVarEditor({
  repositoryId,
  onSaved,
}: {
  repositoryId: string;
  onSaved?: (count: number) => void;
}) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pasting, setPasting] = useState(false);
  const [pasted, setPasted] = useState("");

  useEffect(() => {
    let active = true;
    listEnvVars(repositoryId)
      .then((variables) => {
        if (active) setRows(variables.map(toRow));
      })
      .catch((err: unknown) => {
        if (active)
          setError(err instanceof Error ? err.message : "Could not load variables.");
      });
    return () => {
      active = false;
    };
  }, [repositoryId]);

  function update(index: number, patch: Partial<Row>) {
    setRows((current) =>
      (current ?? []).map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
    setSaved(null);
  }

  function addRow() {
    setRows((current) => [...(current ?? []), { ...BLANK }]);
    setSaved(null);
  }

  function removeRow(index: number) {
    setRows((current) => (current ?? []).filter((_, i) => i !== index));
    setSaved(null);
  }

  function applyPaste() {
    const parsed = parseDotEnv(pasted);
    if (parsed.length > 0) {
      setRows((current) => {
        const kept = (current ?? []).filter(
          (row) => row.key && !parsed.some((p) => p.key === row.key),
        );
        return [...kept, ...parsed];
      });
    }
    setPasted("");
    setPasting(false);
    setSaved(null);
  }

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const payload: EnvVarInput[] = (rows ?? [])
        .filter((row) => row.key.trim())
        .map((row) => ({
          key: row.key.trim(),
          // Empty box on a stored secret means "unchanged".
          value:
            row.storedSecret && row.value === "" ? null : row.value,
          is_secret: row.is_secret,
        }));

      const result = await saveEnvVars(repositoryId, payload);
      setRows(result.map(toRow));
      setSaved(
        result.length === 0
          ? "Cleared — no environment variables."
          : `Saved ${result.length} variable${result.length === 1 ? "" : "s"}.`,
      );
      onSaved?.(result.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  if (rows === null) {
    return (
      <p className="text-sm text-[var(--muted)]">Loading environment variables…</p>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="font-semibold">Environment variables</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Passed to the build. Values are encrypted before they are stored.
          </p>
        </div>
        <button
          onClick={() => setPasting((p) => !p)}
          className="text-sm text-[var(--muted)] underline underline-offset-4 transition hover:text-[var(--foreground)]"
        >
          {pasting ? "Cancel paste" : "Paste a .env file"}
        </button>
      </div>

      {pasting && (
        <div className="mt-3">
          <textarea
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            rows={5}
            placeholder={"DATABASE_URL=postgres://…\nDEBUG=false"}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-xs outline-none focus:border-[var(--accent)]"
          />
          <button
            onClick={applyPaste}
            className="mt-2 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium transition hover:bg-[var(--background)]"
          >
            Add {parseDotEnv(pasted).length || ""} variables
          </button>
        </div>
      )}

      <div className="mt-4 space-y-2">
        {rows.map((row, index) => (
          <div key={index} className="flex flex-wrap items-center gap-2">
            <input
              value={row.key}
              onChange={(e) => update(index, { key: e.target.value })}
              placeholder="KEY"
              spellCheck={false}
              className="w-full min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 font-mono text-sm outline-none focus:border-[var(--accent)] sm:w-auto sm:max-w-[14rem]"
            />
            <input
              value={row.value}
              onChange={(e) => update(index, { value: e.target.value })}
              type={row.is_secret ? "password" : "text"}
              placeholder={
                row.storedSecret && row.value === ""
                  ? "•••••••• (unchanged)"
                  : "value"
              }
              spellCheck={false}
              className="w-full min-w-0 flex-[2] rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 font-mono text-sm outline-none focus:border-[var(--accent)]"
            />
            <label className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
              <input
                type="checkbox"
                checked={row.is_secret}
                onChange={(e) => update(index, { is_secret: e.target.checked })}
              />
              secret
            </label>
            <button
              onClick={() => removeRow(index)}
              aria-label={`Remove ${row.key || "variable"}`}
              className="rounded-md border border-[var(--border)] px-2.5 py-1.5 text-sm text-[var(--muted)] transition hover:border-red-300 hover:text-red-600"
            >
              ✕
            </button>
          </div>
        ))}

        {rows.length === 0 && (
          <p className="rounded-lg border border-dashed border-[var(--border)] p-4 text-center text-sm text-[var(--muted)]">
            No environment variables. Many apps need none.
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          onClick={addRow}
          className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium transition hover:bg-[var(--background)]"
        >
          + Add variable
        </button>
        <button
          onClick={() => void save()}
          disabled={busy}
          className="rounded-md bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] transition hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save variables"}
        </button>

        {saved && (
          <span className="text-sm text-emerald-700 dark:text-emerald-300">
            {saved}
          </span>
        )}
        {error && (
          <span className="text-sm text-red-700 dark:text-red-300">{error}</span>
        )}
      </div>

      <p className="mt-3 text-xs text-[var(--muted)]">
        Tick <strong>secret</strong> for anything sensitive — a secret&apos;s value
        is never sent back to the browser after it is saved, so its box shows a
        mask and leaving it empty keeps the stored value.
      </p>
    </div>
  );
}
