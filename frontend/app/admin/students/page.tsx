/**
 * Student administration: who is on the platform and what they may do.
 *
 * Three distinct levers, kept visibly distinct because they answer different
 * problems and are not interchangeable:
 *
 *   Limit          how many apps this student may run at once
 *   Block deploys  they keep their account and history, but cannot add load
 *   Disable        they cannot log in at all
 *
 * Reaching for "disable" when a student's app is misbehaving is the mistake
 * this layout is designed to prevent.
 */

"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import RequireAuth from "@/components/RequireAuth";
import StatusBadge from "@/components/StatusBadge";
import {
  Alert,
  Eyebrow,
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  SectionTitle,
  Skeleton,
  cx,
  relativeTime,
} from "@/components/ui";
import {
  BanIcon,
  BoxIcon,
  CheckIcon,
  ExternalIcon,
  GitHubIcon,
  SearchIcon,
  ShieldIcon,
  UsersIcon,
} from "@/components/Icons";
import {
  getOverview,
  updateUser,
  type UserChanges,
  type UserWithDeployments,
} from "@/lib/admin";
import { isRunning } from "@/lib/deployments";

export default function AdminStudentsPage() {
  return <RequireAuth adminOnly>{(me) => <Students adminId={me.id} />}</RequireAuth>;
}

type Filter = "all" | "blocked" | "disabled" | "active";

function Students({ adminId }: { adminId: string }) {
  const [users, setUsers] = useState<UserWithDeployments[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const load = useCallback(async () => {
    try {
      setUsers(await getOverview());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load accounts.");
    }
  }, []);

  useEffect(() => {
    // The loader is async: every setState inside it runs after an await, not
    // during this effect. The rule cannot see through the call, so it is
    // silenced here rather than contorting the fetch to satisfy a heuristic.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    if (!users) return null;
    const q = query.trim().toLowerCase();
    return users.filter((u) => {
      if (filter === "blocked" && u.can_deploy) return false;
      if (filter === "disabled" && u.is_active) return false;
      if (filter === "active" && (!u.is_active || !u.can_deploy)) return false;
      if (!q) return true;
      return (
        u.email.toLowerCase().includes(q) ||
        (u.github_username ?? "").toLowerCase().includes(q)
      );
    });
  }, [users, query, filter]);

  const counts = useMemo(
    () => ({
      all: users?.length ?? 0,
      active: users?.filter((u) => u.is_active && u.can_deploy).length ?? 0,
      blocked: users?.filter((u) => !u.can_deploy).length ?? 0,
      disabled: users?.filter((u) => !u.is_active).length ?? 0,
    }),
    [users],
  );

  return (
    <div className="space-y-8">
      <div>
        <Eyebrow>Accounts</Eyebrow>
        <h1 className="mt-3 text-[2rem] font-semibold leading-tight">Students</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Every account, what it is running, and what it is permitted to do.
        </p>
      </div>

      {error && <Alert>{error}</Alert>}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-dim)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by email or GitHub username…"
            className="w-full rounded-full border border-[var(--hairline-strong)] bg-[var(--surface-2)] py-2.5 pl-10 pr-4 text-sm shadow-[var(--bevel)] placeholder:text-[var(--text-dim)] transition-[border-color,background-color] duration-[var(--t-hover)] focus:border-[var(--accent-line)] focus:bg-[var(--surface-3)] focus:outline-none"
          />
        </div>
        <div className="flex rounded-full border border-[var(--hairline)] bg-[var(--surface-2)] p-1 shadow-[var(--bevel)]">
          {(["all", "active", "blocked", "disabled"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cx(
                "rounded-full px-3.5 py-1.5 text-xs font-medium capitalize",
                "transition-[background-color,color] duration-[var(--t-hover)] ease-[var(--ease-out)]",
                filter === f
                  ? "bg-[var(--solid)] text-[var(--solid-text)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text)]",
              )}
            >
              {f} <span className="tabular opacity-70">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      <section>
        <SectionTitle hint="Newest accounts first.">
          <span className="inline-flex items-center gap-2">
            <UsersIcon />
            Accounts
          </span>
        </SectionTitle>

        {filtered === null ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<UsersIcon className="h-10 w-10" />}
            title={users?.length === 0 ? "No accounts yet" : "No matches"}
          >
            {users?.length === 0
              ? "Students appear here as soon as they sign up."
              : "Try a different search or filter."}
          </EmptyState>
        ) : (
          <div className="space-y-3">
            {filtered.map((u) => (
              <StudentRow
                key={u.id}
                user={u}
                isSelf={u.id === adminId}
                onChanged={load}
                onError={setError}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StudentRow({
  user,
  isSelf,
  onChanged,
  onError,
}: {
  user: UserWithDeployments;
  isSelf: boolean;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [quota, setQuota] = useState(user.max_deployments);
  const [blocking, setBlocking] = useState(false);
  const [reason, setReason] = useState("");

  async function change(name: string, changes: UserChanges) {
    setBusy(name);
    onError("");
    try {
      await updateUser(user.id, changes);
      onChanged();
      setBlocking(false);
      setReason("");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not update the account.");
      setQuota(user.max_deployments);
    } finally {
      setBusy(null);
    }
  }

  const atLimit = user.running_count >= user.max_deployments;

  return (
    <Card className={cx(!user.is_active && "opacity-70")}>
      <div className="flex flex-wrap items-start justify-between gap-4 p-5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate font-medium">{user.email}</span>
            {user.role === "admin" && (
              <Badge tone="accent">
                <ShieldIcon className="h-3 w-3" />
                Admin
              </Badge>
            )}
            {!user.is_active && <Badge tone="danger">Account disabled</Badge>}
            {user.is_active && !user.can_deploy && (
              <Badge tone="warn">
                <BanIcon className="h-3 w-3" />
                Deploys blocked
              </Badge>
            )}
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-dim)]">
            {user.github_username ? (
              <span className="inline-flex items-center gap-1.5">
                <GitHubIcon className="h-3.5 w-3.5" />
                {user.github_username}
              </span>
            ) : (
              <span>GitHub not connected</span>
            )}
            <span>{user.repository_count} targets</span>
            <span
              className={cx("tabular", atLimit && user.running_count > 0 && "text-[var(--warn)]")}
            >
              {user.running_count} / {user.max_deployments} running
            </span>
            <span>joined {relativeTime(user.created_at)}</span>
          </div>

          {!user.can_deploy && user.deploy_block_reason && (
            <p className="mt-2 rounded-[var(--r-sm)] bg-[var(--warn-soft)] px-3 py-2 text-xs text-[var(--warn)]">
              <span className="font-semibold">Reason shown to student:</span>{" "}
              {user.deploy_block_reason}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            Limit
            <input
              type="number"
              min={0}
              max={50}
              value={quota}
              disabled={busy !== null}
              onChange={(e) => setQuota(Number(e.target.value))}
              onBlur={() => {
                if (quota !== user.max_deployments) {
                  change("quota", { max_deployments: quota });
                }
              }}
              className="tabular w-16 rounded-[var(--r-sm)] border border-[var(--hairline-strong)] bg-[var(--surface-2)] px-2 py-1 text-center text-sm focus:border-[var(--accent-line)] focus:outline-none"
            />
          </label>

          {user.can_deploy ? (
            <Button
              size="sm"
              disabled={isSelf || busy !== null}
              onClick={() => setBlocking((b) => !b)}
              title={
                isSelf
                  ? "You cannot revoke your own deploy permission"
                  : "Stop this student creating or starting deployments"
              }
            >
              <BanIcon className="h-3.5 w-3.5" />
              Block deploys
            </Button>
          ) : (
            <Button
              size="sm"
              variant="primary"
              loading={busy === "unblock"}
              onClick={() => change("unblock", { can_deploy: true })}
            >
              <CheckIcon className="h-3.5 w-3.5" />
              Allow deploys
            </Button>
          )}

          <Button
            size="sm"
            variant={user.is_active ? "danger" : "primary"}
            loading={busy === "active"}
            disabled={isSelf}
            onClick={() => change("active", { is_active: !user.is_active })}
            title={
              isSelf
                ? "You cannot disable your own account"
                : user.is_active
                  ? "Prevent this account logging in at all"
                  : "Restore access"
            }
          >
            {user.is_active ? "Disable" : "Enable"}
          </Button>

          {user.deployments.length > 0 && (
            <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>
              {open ? "Hide" : `${user.deployments.length} project${user.deployments.length === 1 ? "" : "s"}`}
            </Button>
          )}
        </div>
      </div>

      {/* --- Block, with a reason the student will see ------------------ */}
      {blocking && (
        <div className="border-t border-[var(--hairline)] bg-[var(--surface-2)]/60 px-5 py-4">
          <p className="mb-2 text-sm font-medium">Block deployments</p>
          <p className="mb-3 text-xs text-[var(--text-muted)]">
            They keep their account and can still see their apps, but cannot
            create, build or start anything. Running apps are left alone — stop
            those from Projects if you need to.
          </p>
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-56 flex-1">
              <Input
                label="Reason (shown to the student)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Repeated crash loops taking down the shared machine"
                maxLength={500}
              />
            </div>
            <Button
              variant="danger"
              loading={busy === "block"}
              onClick={() =>
                change("block", {
                  can_deploy: false,
                  deploy_block_reason: reason.trim() || null,
                })
              }
            >
              Block
            </Button>
            <Button variant="ghost" onClick={() => setBlocking(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* --- Their projects -------------------------------------------- */}
      {open && (
        <div className="border-t border-[var(--hairline)] bg-[var(--surface-2)]/50 px-5 py-4">
          <div className="space-y-2">
            {user.deployments.map((d) => (
              <div
                key={d.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--r-sm)] bg-[var(--surface)] px-3 py-2.5"
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  <BoxIcon className="h-4 w-4 shrink-0 text-[var(--text-dim)]" />
                  <span className="truncate text-sm">{d.target_label}</span>
                  <StatusBadge status={d.status} />
                  {d.suspended_by_admin && <Badge tone="danger">Suspended</Badge>}
                </span>
                <span className="flex items-center gap-3">
                  {isRunning(d.status) && d.url && (
                    <a
                      href={d.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs text-[var(--ok)] hover:underline"
                    >
                      {d.url.replace(/^https?:\/\//, "")}
                      <ExternalIcon className="h-3 w-3" />
                    </a>
                  )}
                  <Link
                    href="/admin/deployments"
                    className="text-xs text-[var(--text-dim)] hover:text-[var(--text)]"
                  >
                    Manage
                  </Link>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
