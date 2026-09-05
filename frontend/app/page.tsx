/**
 * The public landing page.
 *
 * It has one job: make it obvious what the platform does before anyone signs
 * up. The pipeline diagram carries most of that, because "we detect, build,
 * store and run it" is a sequence, and a sequence is easier to see than read.
 */

import Link from "next/link";

import {
  BoxIcon,
  CheckIcon,
  DockerIcon,
  GitHubIcon,
  LogoMark,
  RocketIcon,
  ServerIcon,
  ShieldIcon,
  TerminalIcon,
} from "@/components/Icons";

export const metadata = {
  title: "DeployForge — deploy from a repository",
  description:
    "Connect a GitHub repository. DeployForge detects how it should be built, builds it, stores the image, and runs it behind its own URL.",
};

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <LogoMark className="h-8 w-8" />
            DeployForge
          </Link>
          <nav className="hidden items-center gap-8 text-sm text-[var(--text-muted)] sm:flex">
            <a href="#pipeline" className="transition-colors hover:text-[var(--text)]">
              How it works
            </a>
            <a href="#features" className="transition-colors hover:text-[var(--text)]">
              Features
            </a>
            <a href="#safety" className="transition-colors hover:text-[var(--text)]">
              Isolation
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="rounded-[var(--radius-sm)] px-3.5 py-2 text-sm font-medium text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
            >
              Log in
            </Link>
            <Link
              href="/signup"
              className="rounded-[var(--radius-sm)] bg-[var(--accent)] px-3.5 py-2 text-sm font-medium text-[var(--accent-text)] transition-colors hover:bg-[var(--accent-hover)]"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* --- Hero -------------------------------------------------------- */}
      <section className="relative overflow-hidden px-6 pb-24 pt-20">
        <div className="aurora" aria-hidden />
        <div className="grid-backdrop" aria-hidden />

        <div className="relative z-10 mx-auto max-w-3xl text-center">
          <span
            className="rise inline-flex items-center gap-2 rounded-full border border-[var(--border-strong)] bg-[var(--surface)] px-3.5 py-1.5 text-xs font-medium text-[var(--text-muted)]"
            style={{ "--delay": "0ms" } as React.CSSProperties}
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--ok)]" />
            Push a repo, get a URL
          </span>

          <h1
            className="rise headline-gradient mt-6 text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl"
            style={{ "--delay": "70ms" } as React.CSSProperties}
          >
            Point it at a repository.
            <br />
            It works out how to run it.
          </h1>

          <p
            className="rise mx-auto mt-6 max-w-xl text-lg leading-relaxed text-[var(--text-muted)]"
            style={{ "--delay": "140ms" } as React.CSSProperties}
          >
            DeployForge reads your code, builds it — from your Dockerfile if you
            have one, with buildpacks if you do not — stores the image, and runs
            it in an isolated container behind its own URL.
          </p>

          <div
            className="rise mt-9 flex flex-wrap items-center justify-center gap-3"
            style={{ "--delay": "210ms" } as React.CSSProperties}
          >
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-[var(--radius-sm)] bg-[var(--accent)] px-5 py-2.5 text-sm font-medium text-[var(--accent-text)] shadow-[var(--shadow)] transition-colors hover:bg-[var(--accent-hover)]"
            >
              <RocketIcon className="h-4 w-4" />
              Deploy your first app
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-[var(--radius-sm)] border border-[var(--border-strong)] bg-[var(--surface)] px-5 py-2.5 text-sm font-medium transition-colors hover:bg-[var(--surface-2)]"
            >
              I already have an account
            </Link>
          </div>
        </div>

        {/* A mock of the real deployment card. */}
        <div
          className="rise relative z-10 mx-auto mt-16 max-w-3xl"
          style={{ "--delay": "280ms" } as React.CSSProperties}
        >
          <div className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-strong)] bg-[var(--surface)] shadow-[var(--shadow-lg)]">
            <div className="flex items-center gap-2 border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
              <span className="h-2.5 w-2.5 rounded-full bg-[var(--danger)]/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-[var(--warn)]/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-[var(--ok)]/70" />
              <span className="ml-3 font-[family-name:var(--font-geist-mono)] text-xs text-[var(--text-dim)]">
                deployforge — my apps
              </span>
            </div>
            <div className="space-y-3 p-5 text-left">
              <MockRow
                name="octocat/portfolio"
                meta="Dockerfile · nginx"
                url="portfolio-a1b2c3.localhost"
                state="running"
              />
              <MockRow
                name="octocat/notes-api (backend/)"
                meta="Buildpack · FastAPI"
                url="notes-api-backend-9f21e4.localhost"
                state="running"
              />
              <MockRow
                name="octocat/dashboard"
                meta="Buildpack · Next.js"
                state="building"
              />
            </div>
          </div>
        </div>
      </section>

      {/* --- Pipeline ---------------------------------------------------- */}
      <section id="pipeline" className="border-t border-[var(--border)] px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold tracking-tight">
              From repository to running app
            </h2>
            <p className="mt-3 text-[var(--text-muted)]">
              Five steps, each one visible while it happens and inspectable when
              it fails.
            </p>
          </div>

          <ol className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
            {[
              {
                icon: <GitHubIcon className="h-5 w-5" />,
                title: "Connect",
                body: "Authorize GitHub. The token is encrypted on the server and never reaches your browser.",
              },
              {
                icon: <TerminalIcon className="h-5 w-5" />,
                title: "Detect",
                body: "The repository is read — never executed — to find a Dockerfile or identify the framework.",
              },
              {
                icon: <DockerIcon className="h-5 w-5" />,
                title: "Build",
                body: "Your Dockerfile if you have one; Cloud Native Buildpacks if you do not.",
              },
              {
                icon: <BoxIcon className="h-5 w-5" />,
                title: "Store",
                body: "The image is pushed to the registry, so it is an artifact you can roll back to.",
              },
              {
                icon: <ServerIcon className="h-5 w-5" />,
                title: "Run",
                body: "Started in an isolated container and published at its own URL through the router.",
              },
            ].map((step, i) => (
              <li
                key={step.title}
                className="rise rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-5"
                style={{ "--delay": `${i * 70}ms` } as React.CSSProperties}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--accent-soft)] text-[var(--accent)]">
                  {step.icon}
                </div>
                <h3 className="mt-4 font-semibold">
                  <span className="mr-1.5 text-[var(--text-dim)]">{i + 1}.</span>
                  {step.title}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-muted)]">
                  {step.body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* --- Features ---------------------------------------------------- */}
      <section
        id="features"
        className="border-t border-[var(--border)] bg-[var(--surface)]/40 px-6 py-24"
      >
        <div className="mx-auto max-w-5xl">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold tracking-tight">
              Everything the deploy actually needs
            </h2>
          </div>

          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                title: "Monorepos, handled",
                body: "A repository with a frontend and a backend has two right answers. DeployForge lists every deployable directory and lets you choose.",
              },
              {
                title: "Two logs, kept apart",
                body: "The build log says why no image was produced. The runtime log says why the app will not stay up. Conflating them is what makes platforms frustrating.",
              },
              {
                title: "Encrypted configuration",
                body: "Environment variables are encrypted at rest and injected at build and run time. Secrets are never sent back to the browser.",
              },
              {
                title: "A URL per app",
                body: "Every deployment gets its own hostname. Ten apps can all listen on port 3000 and none of them collide.",
              },
              {
                title: "Images you keep",
                body: "Every build is pushed to a registry, so what ran is a stored artifact rather than a tag that exists on one machine.",
              },
              {
                title: "A full history",
                body: "Download, build, push, start, stop — every step is recorded, so a failure points at the stage that caused it.",
              },
            ].map((feature, i) => (
              <div
                key={feature.title}
                className="rise rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-5"
                style={{ "--delay": `${i * 55}ms` } as React.CSSProperties}
              >
                <div className="flex items-center gap-2 text-[var(--accent)]">
                  <CheckIcon className="h-4 w-4" />
                  <h3 className="font-semibold text-[var(--text)]">
                    {feature.title}
                  </h3>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">
                  {feature.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --- Isolation --------------------------------------------------- */}
      <section id="safety" className="border-t border-[var(--border)] px-6 py-24">
        <div className="mx-auto grid max-w-5xl gap-12 lg:grid-cols-2 lg:items-center">
          <div>
            <div className="inline-flex h-11 w-11 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--accent-soft)] text-[var(--accent)]">
              <ShieldIcon className="h-5 w-5" />
            </div>
            <h2 className="mt-5 text-3xl font-semibold tracking-tight">
              One machine, many students
            </h2>
            <p className="mt-4 leading-relaxed text-[var(--text-muted)]">
              Every app runs in its own container on a shared private network,
              with no port published to the host. The router is the only way in,
              and it only knows about apps that are supposed to be running.
            </p>
            <p className="mt-3 leading-relaxed text-[var(--text-muted)]">
              Each container is capped on memory, CPU and process count, and
              cannot gain privileges. One runaway app cannot take the machine
              down for the rest of the class — and an administrator can suspend
              any app without touching the others.
            </p>
          </div>

          <div className="space-y-3">
            {[
              ["Per-app memory and CPU limits", "512 MB and one core by default"],
              ["No new privileges", "containers cannot escalate"],
              ["No published host ports", "reachable only through the router"],
              ["Per-account quotas", "how many apps one student may run at once"],
              ["Admin suspend", "stops an app the owner cannot simply restart"],
            ].map(([title, body]) => (
              <div
                key={title}
                className="flex items-start gap-3 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
              >
                <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--ok)]" />
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-xs text-[var(--text-dim)]">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* --- CTA --------------------------------------------------------- */}
      <section className="border-t border-[var(--border)] px-6 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight">
            Deploy something in the next five minutes
          </h2>
          <p className="mt-3 text-[var(--text-muted)]">
            Create an account, connect GitHub, pick a repository. That is the
            whole setup.
          </p>
          <Link
            href="/signup"
            className="mt-8 inline-flex items-center gap-2 rounded-[var(--radius-sm)] bg-[var(--accent)] px-5 py-2.5 text-sm font-medium text-[var(--accent-text)] shadow-[var(--shadow)] transition-colors hover:bg-[var(--accent-hover)]"
          >
            <RocketIcon className="h-4 w-4" />
            Get started
          </Link>
        </div>
      </section>

      <footer className="border-t border-[var(--border)] px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 text-sm text-[var(--text-dim)]">
          <span className="flex items-center gap-2">
            <LogoMark className="h-6 w-6" />
            DeployForge
          </span>
          <span>Building and running student projects, one repository at a time.</span>
        </div>
      </footer>
    </div>
  );
}

/* --- Hero mock ---------------------------------------------------------- */

function MockRow({
  name,
  meta,
  url,
  state,
}: {
  name: string;
  meta: string;
  url?: string;
  state: "running" | "building";
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{name}</p>
        <p className="mt-0.5 text-xs text-[var(--text-dim)]">{meta}</p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {url && (
          <span className="hidden font-[family-name:var(--font-geist-mono)] text-xs text-[var(--ok)] sm:block">
            {url}
          </span>
        )}
        {state === "running" ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--ok)]/30 bg-[var(--ok-soft)] px-2.5 py-0.5 text-xs font-medium text-[var(--ok)]">
            <span className="live-dot inline-block h-2 w-2 rounded-full bg-[var(--ok)]" />
            Running
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--info)]/30 bg-[var(--info-soft)] px-2.5 py-0.5 text-xs font-medium text-[var(--info)]">
            Building
          </span>
        )}
      </div>
    </div>
  );
}
