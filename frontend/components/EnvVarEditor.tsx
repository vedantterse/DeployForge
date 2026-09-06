"use client";

import { useEffect, useState } from "react";
import { Button, Skeleton } from "@/components/ui";
import { TrashIcon } from "@/components/Icons";
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
      <div className="space-y-2">
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-[var(--text-muted)]">
          {rows.length === 0
            ? "None set. Many apps need none."
            : `${rows.length} variable${rows.length === 1 ? "" : "s"}.`}
        </p>
        <Button size="sm" variant="ghost" onClick={() => setPasting((p) => !p)}>
          {pasting ? "Cancel" : "Paste a .env file"}
        </Button>
      </div>

      {pasting && (
        <div className="mt-3">
          <textarea
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            rows={5}
            spellCheck={false}
            placeholder={"DATABASE_URL=postgres://…\nDEBUG=false"}
            className="w-full rounded-[var(--r-sm)] border border-[var(--hairline-strong)] bg-[var(--surface-2)] p-3 font-[family-name:var(--font-jetbrains-mono)] text-xs outline-none focus:border-[var(--accent-line)]"
          />
          <Button size="sm" className="mt-2" onClick={applyPaste}>
            Add {parseDotEnv(pasted).length || ""} variables
          </Button>
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
              className="w-full min-w-0 flex-1 rounded-[var(--r-sm)] border border-[var(--hairline-strong)] bg-[var(--surface-2)] px-3 py-2 font-[family-name:var(--font-jetbrains-mono)] text-sm outline-none focus:border-[var(--accent-line)] sm:w-auto sm:max-w-[14rem]"
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
              className="w-full min-w-0 flex-[2] rounded-[var(--r-sm)] border border-[var(--hairline-strong)] bg-[var(--surface-2)] px-3 py-2 font-[family-name:var(--font-jetbrains-mono)] text-sm outline-none focus:border-[var(--accent-line)]"
            />
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-[var(--text-muted)]">
              <input
                type="checkbox"
                checked={row.is_secret}
                onChange={(e) => update(index, { is_secret: e.target.checked })}
                className="accent-[var(--accent)]"
              />
              secret
            </label>
            <button
              onClick={() => removeRow(index)}
              aria-label={`Remove ${row.key || "variable"}`}
              className="rounded-[var(--r-sm)] border border-[var(--hairline-strong)] p-2 text-[var(--text-dim)] transition-colors hover:border-[var(--danger)] hover:text-[var(--danger)]"
            >
              <TrashIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}

        {rows.length === 0 && (
          <p className="rounded-[var(--r-sm)] border border-dashed border-[var(--hairline-strong)] p-5 text-center text-sm text-[var(--text-dim)]">
            No environment variables yet.
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button size="sm" onClick={addRow}>
          Add variable
        </Button>
        <Button
          size="sm"
          variant="primary"
          loading={busy}
          onClick={() => void save()}
        >
          Save variables
        </Button>

        {saved && (
          <span className="text-sm text-[var(--ok)]">{saved}</span>
        )}
        {error && <span className="text-sm text-[var(--danger)]">{error}</span>}
      </div>

      <p className="mt-3 text-xs text-[var(--text-dim)]">
        Tick <strong className="font-medium text-[var(--text-muted)]">secret</strong>{" "}
        for anything sensitive — a secret&apos;s value is never sent back to the
        browser after it is saved, so its box shows a mask and leaving it empty
        keeps the stored value. Restart the app for changes to take effect.
      </p>
    </div>
  );
}
