import Link from "next/link";
import { ForgeIcon } from "@/components/Icons";

/** Public header for the landing page. */
export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--background)]/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
            <ForgeIcon className="h-5 w-5" />
          </span>
          DeployForge
        </Link>

        <nav className="hidden items-center gap-7 text-sm text-[var(--muted)] sm:flex">
          <a href="#features" className="transition hover:text-[var(--foreground)]">
            Features
          </a>
          <a href="#how" className="transition hover:text-[var(--foreground)]">
            How it works
          </a>
          <a href="#safety" className="transition hover:text-[var(--foreground)]">
            Safety
          </a>
        </nav>

        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className="rounded-lg px-3 py-2 text-sm font-medium text-[var(--muted)] transition hover:text-[var(--foreground)]"
          >
            Log in
          </Link>
          <Link
            href="/signup"
            className="rounded-lg bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] transition hover:opacity-90"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}
