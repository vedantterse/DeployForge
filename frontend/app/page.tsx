import Link from "next/link";
import DetectionPreview from "@/components/DetectionPreview";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";
import {
  ArrowIcon,
  CubeIcon,
  DatabaseIcon,
  GitHubIcon,
  ShieldIcon,
  TargetIcon,
  UsersIcon,
} from "@/components/Icons";

const FEATURES = [
  {
    icon: GitHubIcon,
    title: "Connect GitHub once",
    body: "Authorize over OAuth. Your credentials never touch DeployForge — the access token is exchanged on the server and stored encrypted at rest.",
  },
  {
    icon: TargetIcon,
    title: "Pick what to deploy",
    body: "Choose a repository, then choose the target inside it. A monorepo's frontend and backend become separate deployments instead of a guess.",
  },
  {
    icon: CubeIcon,
    title: "Docker or framework, detected",
    body: "A Dockerfile or compose file wins. Otherwise DeployForge identifies the framework and selects a buildpack — with the evidence it matched.",
  },
  {
    icon: ShieldIcon,
    title: "Nothing is executed",
    body: "Your code is downloaded to a temporary directory, read, and deleted. No scripts run, no build hooks fire, nothing is kept on disk.",
  },
  {
    icon: DatabaseIcon,
    title: "Every result recorded",
    body: "Each analysis writes a deployment record: what was detected, which commit, and when. The whole platform state lives in the database.",
  },
  {
    icon: UsersIcon,
    title: "Admin and user roles",
    body: "Users manage their own deployments. Admins see every account and everything deployed across the platform, enforced server-side.",
  },
];

const STACKS = [
  "Docker",
  "Compose",
  "Django",
  "FastAPI",
  "Flask",
  "Next.js",
  "React",
  "Express",
  "Go",
  "Java",
  "Ruby",
  "PHP",
];

const STEPS = [
  {
    label: "Sign up",
    detail: "Email and password. Roles are built in from the start.",
  },
  {
    label: "Authorize GitHub",
    detail: "Read access to your repositories, revocable at any time.",
  },
  {
    label: "Pick a target",
    detail: "A repository, and the directory inside it that holds the app.",
  },
  {
    label: "See the verdict",
    detail: "Docker or framework, the build method, and the files that proved it.",
  },
];

export default function Home() {
  return (
    <>
      <SiteHeader />

      <main className="flex-1">
        {/* ---------------- Hero ---------------- */}
        <section className="relative overflow-hidden border-b border-[var(--border)]">
          <div className="grid-backdrop" />
          <div className="hero-glow" />

          <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-16 sm:pt-24">
            <div className="grid items-center gap-14 lg:grid-cols-2">
              <div>
                <span
                  className="rise inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--panel)] px-3 py-1 text-xs font-medium text-[var(--muted)]"
                  style={{ "--delay": "0ms" } as React.CSSProperties}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Phase 1 · Repository detection
                </span>

                <h1
                  className="rise headline-gradient mt-6 text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-[3.4rem]"
                  style={{ "--delay": "80ms" } as React.CSSProperties}
                >
                  Point it at a repository.
                  <br />
                  It works out how to run it.
                </h1>

                <p
                  className="rise mt-6 max-w-xl text-lg leading-relaxed text-[var(--muted)]"
                  style={{ "--delay": "160ms" } as React.CSSProperties}
                >
                  DeployForge inspects your code and decides whether it should be
                  built with Docker or a buildpack — reading files, never running
                  them.
                </p>

                <div
                  className="rise mt-9 flex flex-wrap items-center gap-3"
                  style={{ "--delay": "240ms" } as React.CSSProperties}
                >
                  <Link
                    href="/signup"
                    className="group inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:brightness-110"
                  >
                    Get started
                    <ArrowIcon className="h-4 w-4 transition group-hover:translate-x-0.5" />
                  </Link>
                  <Link
                    href="/login"
                    className="rounded-lg border border-[var(--border)] bg-[var(--panel)] px-5 py-3 text-sm font-semibold transition hover:border-[var(--accent)]"
                  >
                    Log in
                  </Link>
                </div>

                <p
                  className="rise mt-6 text-xs text-[var(--muted)]"
                  style={{ "--delay": "320ms" } as React.CSSProperties}
                >
                  No deployment yet — Phase 1 understands the input. Building and
                  running come next.
                </p>
              </div>

              <div
                className="rise"
                style={{ "--delay": "200ms" } as React.CSSProperties}
              >
                <DetectionPreview />
              </div>
            </div>
          </div>
        </section>

        {/* ---------------- Stack strip ---------------- */}
        <section className="border-b border-[var(--border)] bg-[var(--panel)]">
          <div className="mx-auto max-w-6xl px-6 py-8">
            <p className="text-center text-xs font-medium uppercase tracking-widest text-[var(--muted)]">
              Recognizes
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2.5">
              {STACKS.map((stack) => (
                <span
                  key={stack}
                  className="rounded-full border border-[var(--border)] px-3.5 py-1.5 text-sm text-[var(--muted)]"
                >
                  {stack}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------- Features ---------------- */}
        <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-20">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-bold tracking-tight">What it does</h2>
            <p className="mt-3 text-[var(--muted)]">
              Six things DeployForge gets right before a single container is ever
              built.
            </p>
          </div>

          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <div
                key={title}
                className="lift rounded-2xl border border-[var(--border)] bg-[var(--panel)] p-6"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
                  <Icon />
                </span>
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------- How it works ---------------- */}
        <section
          id="how"
          className="scroll-mt-20 border-y border-[var(--border)] bg-[var(--panel)]"
        >
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="grid gap-14 lg:grid-cols-2">
              <div>
                <h2 className="text-3xl font-bold tracking-tight">How it works</h2>
                <p className="mt-3 text-[var(--muted)]">
                  Four steps from a blank account to a stored verdict.
                </p>

                <ol className="mt-10 space-y-8">
                  {STEPS.map((step, index) => (
                    <li key={step.label} className="relative flex gap-4 pl-1">
                      {index < STEPS.length - 1 && (
                        <span
                          className="absolute left-[1.05rem] top-9 h-full w-px bg-[var(--border)]"
                          aria-hidden
                        />
                      )}
                      <span className="relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--background)] text-sm font-semibold">
                        {index + 1}
                      </span>
                      <div className="pt-1">
                        <h3 className="font-semibold">{step.label}</h3>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                          {step.detail}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>

              {/* What the detector actually looks at */}
              <div className="rounded-2xl border border-[var(--border)] bg-[var(--background)] p-1">
                <div className="rounded-xl bg-[var(--panel)] p-5 font-mono text-xs leading-relaxed">
                  <p className="text-[var(--muted)]">
                    # what the detector looks for, in order
                  </p>
                  <div className="mt-4 space-y-2.5">
                    {[
                      ["Dockerfile", "→ docker", true],
                      ["docker-compose.yml", "→ docker + compose", true],
                      ["package.json", "→ next / react / express", false],
                      ["requirements.txt", "→ django / fastapi / flask", false],
                      ["pyproject.toml, manage.py", "→ python", false],
                      ["go.mod, pom.xml, Gemfile", "→ go / java / ruby", false],
                    ].map(([file, verdict, isDocker]) => (
                      <div key={file as string} className="flex flex-wrap items-baseline gap-2">
                        <span
                          className={
                            isDocker
                              ? "text-sky-600 dark:text-sky-400"
                              : "text-emerald-600 dark:text-emerald-400"
                          }
                        >
                          {file}
                        </span>
                        <span className="text-[var(--muted)]">{verdict}</span>
                      </div>
                    ))}
                  </div>
                  <p className="mt-5 border-t border-[var(--border)] pt-4 text-[var(--muted)]">
                    no match → unknown, with a reason. never an exception.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------------- Safety ---------------- */}
        <section id="safety" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-20">
          <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--panel)]">
            <div className="grid gap-10 p-8 sm:p-12 lg:grid-cols-[1.1fr_1fr]">
              <div>
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
                  <ShieldIcon className="h-6 w-6" />
                </span>
                <h2 className="mt-5 text-2xl font-bold tracking-tight">
                  Your code is read, never run
                </h2>
                <p className="mt-3 leading-relaxed text-[var(--muted)]">
                  Detection is pure filesystem inspection. DeployForge downloads an
                  archive rather than cloning, so no credential helper, submodule
                  or hook is ever invoked — and the download is deleted before the
                  response returns.
                </p>
              </div>

              <ul className="space-y-3 text-sm">
                {[
                  "Archive download — not git clone, so nothing is configured or executed",
                  "Extraction blocks path traversal, symlinks and device files",
                  "Size and file-count caps stop a hostile archive filling the disk",
                  "Temporary directory removed in a finally, even when a request fails",
                  "GitHub tokens encrypted with Fernet; never sent to the browser",
                  "The client secret and token exchange stay on the server",
                ].map((item) => (
                  <li key={item} className="flex gap-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                      ✓
                    </span>
                    <span className="text-[var(--muted)]">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ---------------- Closing CTA ---------------- */}
        <section className="mx-auto max-w-6xl px-6 pb-24">
          <div className="relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--panel)] px-8 py-14 text-center">
            <div className="hero-glow opacity-70" />
            <div className="relative">
              <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
                Ready to try it?
              </h2>
              <p className="mx-auto mt-3 max-w-md text-[var(--muted)]">
                Create an account, connect GitHub, and pick a repository. It takes
                about a minute.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link
                  href="/signup"
                  className="group inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:brightness-110"
                >
                  Sign up
                  <ArrowIcon className="h-4 w-4 transition group-hover:translate-x-0.5" />
                </Link>
                <Link
                  href="/login"
                  className="rounded-lg border border-[var(--border)] px-5 py-3 text-sm font-semibold transition hover:border-[var(--accent)]"
                >
                  Log in
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}
