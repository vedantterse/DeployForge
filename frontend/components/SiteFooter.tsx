import Link from "next/link";
import { ForgeIcon } from "@/components/Icons";

export default function SiteFooter() {
  return (
    <footer className="border-t border-[var(--border)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 text-sm text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <ForgeIcon className="h-5 w-5" />
          <span className="font-medium text-[var(--foreground)]">DeployForge</span>
          <span className="ml-2 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs">
            Phase 1 · Detection
          </span>
        </div>
        <div className="flex items-center gap-5">
          <Link href="/login" className="transition hover:text-[var(--foreground)]">
            Log in
          </Link>
          <Link href="/signup" className="transition hover:text-[var(--foreground)]">
            Sign up
          </Link>
        </div>
      </div>
    </footer>
  );
}
