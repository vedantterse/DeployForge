/**
 * The public landing page.
 *
 * It has one job: make it obvious what the platform does before anyone signs
 * up. The pipeline carries most of that, because "detect, build, store, run"
 * is a sequence, and a sequence is easier to see than to read.
 *
 * The header knows whether you are already signed in, so a returning visitor
 * is offered their dashboard rather than a login form.
 */

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Button, Card, Eyebrow, Reveal, cx } from "@/components/ui";
import {
  ArrowRight,
  BoxIcon,
  CheckIcon,
  DockerIcon,
  LayersIcon,
  LogoMark,
  RocketIcon,
  ServerIcon,
  ShieldIcon,
  TerminalIcon,
} from "@/components/Icons";
import { getCurrentUser, homeFor, type User } from "@/lib/auth";

export default function LandingPage() {
  // `undefined` while the stored session is being checked, so the header does
  // not flash "Log in" at someone who is already signed in.
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    getCurrentUser().then((u) => active && setUser(u ?? null));
    return () => {
      active = false;
    };
  }, []);

  const home = user ? homeFor(user) : "/signup";

  return (
    <div className="min-h-screen bg-[var(--bg)]">
      {/* --- Header: a floating glass pill, detached from the top -------- */}
      <header className="sticky top-0 z-30 px-4 pt-4">
        <div className="glass mx-auto flex max-w-5xl items-center justify-between gap-4 rounded-full py-2.5 pl-5 pr-2.5">
          <Link href="/" className="flex items-center gap-2.5 font-semibold">
            <LogoMark className="h-7 w-7" />
            <span className="text-[15px]">DeployForge</span>
          </Link>

          <nav className="hidden items-center gap-7 text-sm text-[var(--text-muted)] md:flex">
            {[
              ["#pipeline", "How it works"],
              ["#features", "Features"],
              ["#isolation", "Isolation"],
            ].map(([href, label]) => (
              <a
                key={href}
                href={href}
                className="transition-colors duration-[var(--t-hover)] hover:text-[var(--text)]"
              >
                {label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            {user === undefined ? (
              // Reserve the space rather than shifting the bar once it loads.
              <span className="h-9 w-[6.5rem] rounded-full bg-[var(--surface-2)]" />
            ) : user ? (
              <Link href={home}>
                <Button variant="primary" trailing={<ArrowRight className="h-3 w-3" />}>
                  Dashboard
                </Button>
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="rounded-full px-3.5 py-2 text-sm font-medium text-[var(--text-muted)] transition-colors duration-[var(--t-hover)] hover:text-[var(--text)]"
                >
                  Log in
                </Link>
                <Link href="/signup">
                  <Button variant="primary">Get started</Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* --- Hero -------------------------------------------------------- */}
      <section className="relative overflow-hidden px-4 pb-28 pt-24 sm:pt-32">
        <div className="mesh" aria-hidden />
        <div className="hairline-grid" aria-hidden />

        <div className="relative z-10 mx-auto max-w-3xl text-center">
          <div className="rise" style={{ "--delay": "0ms" } as React.CSSProperties}>
            <Eyebrow>
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--ok)]" />
              Push a repo, get a URL
            </Eyebrow>
          </div>

          <h1
            className="rise headline mx-auto mt-7 max-w-[15ch] text-[3.25rem] font-semibold leading-[1.02] sm:text-[4.25rem]"
            style={{ "--delay": "80ms" } as React.CSSProperties}
          >
            Point it at a repository. It works out how to run it.
          </h1>

          <p
            className="rise mx-auto mt-7 max-w-xl text-[17px] leading-relaxed text-[var(--text-muted)]"
            style={{ "--delay": "160ms" } as React.CSSProperties}
          >
            DeployForge reads your code and builds it — your Dockerfile, your
            whole Compose stack, or buildpacks when there is neither — stores the
            image, and runs it isolated behind its own URL.
          </p>

          <div
            className="rise mt-10 flex flex-wrap items-center justify-center gap-3"
            style={{ "--delay": "240ms" } as React.CSSProperties}
          >
            <Link href={home}>
              <Button
                variant="primary"
                size="lg"
                trailing={<ArrowRight className="h-3.5 w-3.5" />}
              >
                {user ? "Open your dashboard" : "Deploy your first app"}
              </Button>
            </Link>
            {!user && (
              <Link href="/login">
                <Button size="lg">I already have an account</Button>
              </Link>
            )}
          </div>
        </div>

        {/* A mock of the real deployment list, in the real chrome. */}
        <div
          className="rise relative z-10 mx-auto mt-20 max-w-3xl"
          style={{ "--delay": "320ms" } as React.CSSProperties}
        >
          <div className="bezel shadow-[var(--shadow-lg)]">
            <div className="overflow-hidden bg-[var(--surface)]">
              <div className="flex items-center gap-2 border-b border-[var(--hairline)] px-4 py-3">
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--danger)]/60" />
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--warn)]/60" />
                <span className="h-2.5 w-2.5 rounded-full bg-[var(--ok)]/60" />
                <span className="ml-3 font-[family-name:var(--font-jetbrains-mono)] text-xs text-[var(--text-dim)]">
                  deployforge — my apps
                </span>
              </div>
              <div className="space-y-2.5 p-4 text-left">
                <MockRow
                  name="octocat/portfolio"
                  meta="Dockerfile"
                  url="portfolio-a1b2c3.localhost"
                  state="running"
                />
                <MockRow
                  name="octocat/shop"
                  meta="Compose · 3 services"
                  url="shop-9f21e4.localhost"
                  state="running"
                />
                <MockRow
                  name="octocat/notes-api (backend/)"
                  meta="Buildpack · FastAPI"
                  state="building"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* --- Pipeline ---------------------------------------------------- */}
      <section
        id="pipeline"
        className="border-t border-[var(--hairline)] px-4 py-28"
      >
        <div className="mx-auto max-w-5xl">
          <Reveal className="mx-auto max-w-2xl text-center">
            <Eyebrow>The pipeline</Eyebrow>
            <h2 className="mt-6 text-[2.5rem] font-semibold leading-tight">
              From repository to running app
            </h2>
            <p className="mt-4 leading-relaxed text-[var(--text-muted)]">
              Five steps, each visible while it happens and inspectable when it
              fails.
            </p>
          </Reveal>

          <ol className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              {
                icon: <TerminalIcon className="h-[18px] w-[18px]" />,
                title: "Connect",
                body: "Authorize GitHub. The token is encrypted on the server and never reaches your browser.",
              },
              {
                icon: <BoxIcon className="h-[18px] w-[18px]" />,
                title: "Detect",
                body: "Your repository is read — never executed — to find a Dockerfile, a Compose stack, or a framework.",
              },
              {
                icon: <DockerIcon className="h-[18px] w-[18px]" />,
                title: "Build",
                body: "Your own Dockerfile, your whole Compose stack, or Cloud Native Buildpacks.",
              },
              {
                icon: <LayersIcon className="h-[18px] w-[18px]" />,
                title: "Store",
                body: "The image goes to the registry, so it is an artifact you can roll back to.",
              },
              {
                icon: <ServerIcon className="h-[18px] w-[18px]" />,
                title: "Run",
                body: "Started in an isolated container and published at its own URL.",
              },
            ].map((step, i) => (
              <Reveal key={step.title} delay={i * 80}>
                <li className="plate h-full p-5">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--accent-line)] bg-[var(--accent-soft)] text-[var(--accent)]">
                    {step.icon}
                  </div>
                  <h3 className="mt-5 font-semibold">
                    <span className="mr-1.5 font-[family-name:var(--font-jetbrains-mono)] text-xs text-[var(--text-dim)]">
                      0{i + 1}
                    </span>
                    {step.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">
                    {step.body}
                  </p>
                </li>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      {/* --- Features ---------------------------------------------------- */}
      <section
        id="features"
        className="border-t border-[var(--hairline)] bg-[var(--bg-deep)] px-4 py-28"
      >
        <div className="mx-auto max-w-5xl">
          <Reveal className="mx-auto max-w-2xl text-center">
            <Eyebrow>Built in</Eyebrow>
            <h2 className="mt-6 text-[2.5rem] font-semibold leading-tight">
              Everything the deploy actually needs
            </h2>
          </Reveal>

          <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                title: "Compose, in full",
                body: "A repository with a compose file runs every service in it — web, database, queue — on its own private network.",
              },
              {
                title: "Monorepos, handled",
                body: "A repository with a frontend and a backend has two right answers. Every deployable directory is offered; you choose.",
              },
              {
                title: "Two logs, kept apart",
                body: "The build log says why no image was produced. The runtime log says why the app will not stay up.",
              },
              {
                title: "Encrypted configuration",
                body: "Environment variables are encrypted at rest and injected at build and run time. Secrets never come back to the browser.",
              },
              {
                title: "A URL per app",
                body: "Every deployment gets its own hostname. Ten apps can all listen on port 3000 and none of them collide.",
              },
              {
                title: "A full history",
                body: "Download, build, push, start, stop — every step recorded, so a failure points at the stage that caused it.",
              },
            ].map((feature, i) => (
              <Reveal key={feature.title} delay={i * 60}>
                <Card interactive className="h-full p-5">
                  <div className="flex items-start gap-2.5">
                    <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--accent)]" />
                    <div>
                      <h3 className="font-semibold">{feature.title}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">
                        {feature.body}
                      </p>
                    </div>
                  </div>
                </Card>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* --- Isolation --------------------------------------------------- */}
      <section
        id="isolation"
        className="border-t border-[var(--hairline)] px-4 py-28"
      >
        <div className="mx-auto grid max-w-5xl gap-14 lg:grid-cols-2 lg:items-center">
          <Reveal>
            <Eyebrow>Shared hardware</Eyebrow>
            <h2 className="mt-6 text-[2.5rem] font-semibold leading-tight">
              One machine, a whole class
            </h2>
            <p className="mt-5 leading-relaxed text-[var(--text-muted)]">
              Every app runs in its own container on a private network, with no
              port published to the host. The router is the only way in, and it
              only knows about apps that are supposed to be running.
            </p>
            <p className="mt-4 leading-relaxed text-[var(--text-muted)]">
              Each container is capped on memory, CPU and process count, and
              cannot gain privileges. One runaway app cannot take the machine
              down for everyone else.
            </p>
          </Reveal>

          <Reveal delay={120} className="space-y-2.5">
            {[
              ["Per-app memory and CPU limits", "512 MB and one core by default"],
              ["No new privileges", "containers cannot escalate"],
              ["No published host ports", "reachable only through the router"],
              ["Private network per stack", "one student's database is not another's"],
              ["Per-account quotas", "how many apps one student may run at once"],
              ["Administrator suspend", "stops an app the owner cannot simply restart"],
            ].map(([title, body]) => (
              <div
                key={title}
                className="flex items-start gap-3 rounded-[var(--r-sm)] border border-[var(--hairline)] bg-[var(--surface)] px-4 py-3"
              >
                <ShieldIcon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--ok)]" />
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-xs text-[var(--text-dim)]">{body}</p>
                </div>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* --- CTA --------------------------------------------------------- */}
      <section className="border-t border-[var(--hairline)] px-4 py-24">
        <Reveal className="mx-auto max-w-2xl text-center">
          <h2 className="text-[2.5rem] font-semibold leading-tight">
            Deploy something in five minutes
          </h2>
          <p className="mt-4 leading-relaxed text-[var(--text-muted)]">
            Create an account, connect GitHub, pick a repository. That is the
            whole setup.
          </p>
          <Link href={home} className="mt-9 inline-block">
            <Button
              variant="primary"
              size="lg"
              trailing={<RocketIcon className="h-3.5 w-3.5" />}
            >
              {user ? "Open your dashboard" : "Get started"}
            </Button>
          </Link>
        </Reveal>
      </section>

      <footer className="border-t border-[var(--hairline)] px-4 py-9">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 text-sm text-[var(--text-dim)]">
          <span className="flex items-center gap-2.5">
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
    <div
      className={cx(
        "flex items-center justify-between gap-4 rounded-[var(--r-sm)] border border-[var(--hairline)]",
        "bg-[var(--surface-2)] px-4 py-3",
      )}
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{name}</p>
        <p className="mt-0.5 text-xs text-[var(--text-dim)]">{meta}</p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {url && (
          <span className="hidden font-[family-name:var(--font-jetbrains-mono)] text-xs text-[var(--ok)] sm:block">
            {url}
          </span>
        )}
        {state === "running" ? (
          <Badge tone="ok">
            <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-[var(--ok)]" />
            Running
          </Badge>
        ) : (
          <Badge tone="info">Building</Badge>
        )}
      </div>
    </div>
  );
}
