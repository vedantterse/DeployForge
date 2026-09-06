# DeployForge

A self-hosted deployment platform. A student connects a GitHub repository;
DeployForge works out how it should be built, builds it, stores the image, and
runs it behind its own URL. An administrator watches the machine they all
share and controls what each account may do.

Built for a class on one server, so quotas, per-app resource limits and
administrator control are part of the design rather than bolted on.

---

## What it does

```
GitHub repo ─> download ─> detect ─> build ─> registry ─> run ─> URL
               (tarball)   (read     (one of      (image    (container)
                            only)     three)      stored)
```

**Three build paths**, chosen from the files actually downloaded — never from a
stale detection row:

| What you picked | How it is built | What runs |
|---|---|---|
| A directory with `docker-compose.yml` | `docker compose up --build` | **every service in the file** |
| A directory with a `Dockerfile` | `docker build` | one container |
| A directory with neither | Cloud Native Buildpacks (`pack`) | one container |
| **Several directories** | each on its own terms, then composed | **all of them, wired together** |

Compose wins over a Dockerfile beside it: when a repository has both, the
compose file is the author saying "this app is these services together".

**Monorepos, together or apart.** A repository with `frontend/` and `backend/`
offers both. Tick one to deploy it alone; tick several and they become **one
deployment** — each directory built on its own terms, then run together on a
private network.

That last part is the point: a frontend is useless without the backend it
calls. Services in a stack reach each other by name, and the address is
injected for them:

```
frontend  ->  BACKEND_URL=http://backend:8080
backend   ->  FRONTEND_URL=http://frontend:8080
```

No hostname is hardcoded, and a variable you set yourself is never overwritten.
One service gets the public URL (a directory named `frontend`, `web`, `client`
… or the first you picked); the rest are reachable only from inside the stack.

**One target, one app.** A target that is already connected is marked in the
repository list and cannot be selected again — a monorepo's *other* directories
stay available.

### Apps and deployments

An **app** is a target a student connected. A **deployment** is one attempt to
build and run it. Rebuilding gives an app another deployment; it does not give
the student another app, and the dashboard counts apps.

Three things follow, and all three are what a student would assume anyway:

- **The URL belongs to the app.** It is derived from the app, not from a build
  of it, so a link that was shared still works after a redeploy. The database
  enforces that only one deployment is live on a hostname at a time.
- **A new deployment replaces the one before it** — but only once it has
  proved it can boot. The old container is stopped after the new one is
  healthy, never before, so a redeploy that fails to start leaves the working
  app up.
- **A failed redeploy does not take an app down.** While something is running,
  that is the app's state; the failure is in the history, where its log is.

Deleting an app removes its containers, its history and the connection, so the
repository can be connected again. Deleting one deployment removes only that
build from the history.

### Routing

Every app gets a hostname: `<repo>-<id6>.localhost`. Browsers resolve
any `*.localhost` name to the loopback address with no DNS or hosts entry,
which is what makes per-app URLs work on a laptop.

Traefik polls `GET /internal/traefik/config` and rebuilds its routing table
from the `deployments` table, so the database is the single source of truth: a
stopped app leaves the routing table within one poll, and no proxy config is
ever written to disk or reloaded by hand.

It also means the proxy needs **no access to the Docker socket** — socket access
is root-equivalent on the host, and granting it to an internet-facing process
to save writing one endpoint would be a poor trade.

### Isolation and control

Each container gets a memory cap, a CPU cap, a PID limit and
`--security-opt no-new-privileges`, and publishes no host port. A compose stack
runs on its own private network, and only its web service is additionally
attached to the shared edge network — one student's database is unreachable
from another student's app.

**`ports:` is removed from a stack's compose file**, and the container port
kept as `expose:`. Publishing a port means claiming it on the machine everyone
shares: every Next.js compose file publishes 3000, so the second student to
deploy one gets `ports are not available`, and a published `5432` would put
their database on the host — exactly what the isolation above exists to
prevent. Nothing is lost: the router reaches a stack by container name over the
shared network, and services still reach each other by service name. The build
log says what was removed rather than rewriting a file silently.

Administrators have three distinct levers, kept separate because they answer
different problems:

| Lever | Effect |
|---|---|
| **Quota** | how many apps this account may run at once (builds of one app count once) |
| **Block deploys** | account keeps working; cannot create, build or start anything |
| **Disable account** | cannot log in at all |
| **Suspend a project** | stopped, and the owner cannot start, delete or re-add it |

Suspension deliberately blocks deletion. Otherwise the owner could delete the
suspended deployment, reconnect the same repository, and have a clean one a
moment later.

---

## Requirements

- **Docker Desktop** (or Docker Engine) — required. Runs PostgreSQL, the
  registry, the router, and every deployed app.
- **Python 3.12+**, **Node.js 20+**
- **`pack` CLI 0.40+** — only for repositories with neither a Dockerfile nor a
  compose file. Everything else works without it.

---

## 1. Infrastructure

Four containers. Run these once; they restart with Docker afterwards.

```bash
docker network create deployforge_edge
```

```bash
docker run -d --name deployforge-db --restart unless-stopped -e POSTGRES_USER=deployforge -e POSTGRES_PASSWORD=deployforge -e POSTGRES_DB=deployforge -p 5433:5432 -v deployforge_pgdata:/var/lib/postgresql/data postgres:17
```

```bash
docker run -d --name deployforge-registry --restart unless-stopped -p 127.0.0.1:5000:5000 -v deployforge_registry:/var/lib/registry --network deployforge_edge registry:2
```

```bash
docker run -d --name deployforge-traefik --restart unless-stopped -p 80:80 -p 127.0.0.1:8090:8080 --network deployforge_edge traefik:v3.3 --api.dashboard=true --api.insecure=true --providers.http.endpoint="http://host.docker.internal:8000/internal/traefik/config?token=CHANGE_ME" --providers.http.pollInterval=5s --entrypoints.web.address=:80
```

The database is published on **5433**, not 5432, so it cannot collide with a
PostgreSQL already on the host. The token in the Traefik command must match
`TRAEFIK_PROVIDER_TOKEN` in `backend/.env`.

Traefik reaches the backend at `host.docker.internal`, which Docker Desktop
provides. On Linux, add `--add-host=host.docker.internal:host-gateway`.

Check all four are up:

```bash
docker ps --filter name=deployforge
```

## 2. Buildpacks (optional)

Only needed for repositories with no Dockerfile and no compose file.

```bash
winget install --id Buildpacks.pack --source winget
```

On macOS use `brew install buildpacks/tap/pack`; otherwise see
<https://buildpacks.io/docs/install-pack/>. Versions below 0.40 use a Docker API
modern daemons reject — check with `pack version`.

If `pack` is not on the server's `PATH`, set `PACK_BINARY` in `backend/.env` to
its full path.

## 3. Backend

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

On Linux/macOS use `.venv/bin/pip` throughout.

## 4. Configuration

```bash
cd backend && cp .env.example .env
```

Generate the two secrets:

```bash
cd backend && .venv/Scripts/python -c "import secrets; from cryptography.fernet import Fernet; print('JWT_SECRET=' + secrets.token_hex(32)); print('TOKEN_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Then edit `backend/.env` and set:

```
DATABASE_URL=postgresql+asyncpg://deployforge:deployforge@localhost:5433/deployforge
JWT_SECRET=<from above>
TOKEN_ENCRYPTION_KEY=<from above>
GITHUB_CLIENT_ID=<from step 5>
GITHUB_CLIENT_SECRET=<from step 5>
TRAEFIK_PROVIDER_TOKEN=<same value used in the Traefik command>
```

> **Never re-copy `.env.example` over a working `.env`.** It resets
> `DATABASE_URL` to port 5432, and replacing `TOKEN_ENCRYPTION_KEY` makes every
> stored GitHub token permanently undecryptable. Edit the lines you need.

Resource limits, quotas and the registry host all have working defaults — see
the comments in `.env.example`.

## 5. GitHub OAuth App

**GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**

| Field | Value |
|---|---|
| Application name | `DeployForge (local)` |
| Homepage URL | `http://localhost:3000` |
| Authorization callback URL | `http://localhost:8000/github/callback` |

The callback must match `GITHUB_CALLBACK_URL` exactly — port **8000**, not
3000. Generate a client secret; it is shown once and can only be replaced,
never retrieved.

Students authorize this same app with their own GitHub accounts.

## 6. Database schema

```bash
cd backend && .venv/Scripts/alembic upgrade head
```

Re-run this after pulling changes; it is safe to run when already up to date.

## 7. Create the administrator

Signing up through the UI **always** creates a normal student account. This
script is the only way an administrator comes into existence:

```bash
cd backend && .venv/Scripts/python -m scripts.create_admin you@example.com
```

It prompts for a password without echoing it. To set one non-interactively:

```bash
cd backend && .venv/Scripts/python -m scripts.create_admin you@example.com --password "your-password"
```

Run against an existing account, it promotes that account to administrator
rather than failing.

## 8. Frontend

```bash
cd frontend && npm install && cp .env.example .env.local
```

## 9. Run

Two terminals.

```bash
cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Open <http://localhost:3000>.

> `.env` changes need a backend **restart** — uvicorn's reloader only watches
> `.py` files, and settings are cached at import. On a synced folder (OneDrive,
> Dropbox) the reloader can miss `.py` changes too; restart by hand if an edit
> seems to have no effect.

## 10. Verify

- <http://localhost:8000/health> reports `"status":"ok"` and `"database":"ok"`.
- Log in as the administrator → **Infrastructure**. Docker, Registry and Router
  should be operational; Buildpacks too if you did step 2.
- <http://localhost:8090> is the Traefik dashboard.

## 11. Tests

```bash
backend/.venv/Scripts/python -m pytest backend/tests/
```

Tests run against the real database inside transactions that roll back, so they
leave no rows behind. Docker and GitHub are stubbed; nothing is built, run or
fetched.

---

## Using it

### As a student

Sign up → **Deploy new** → **Authorize GitHub** → pick a repository → pick what
inside it to deploy → **Build and deploy** → **Start**.

That creates an app. Opening it shows its URL, its environment variables and
every build it has had; **Redeploy** builds it again from the latest commit.

The build runs in the background and its log streams on the deployment page.
The first buildpack build on a machine downloads a large builder image, so it
takes a while; Dockerfile and Compose builds have no such cost.

Two logs are kept apart on purpose:

- the **build log** says why no image could be produced. Recognised failures
  are explained in plain words on the deployment itself — "change `next build
  --turbopack` to `next build`" rather than "exit status 1";
- the **runtime log** says why the app that was built will not stay up. For a
  compose stack it covers every service, because the reason the web service is
  failing is usually printed by the database next to it.

Both are read the same way: a container that dies on boot has its output
matched against known failures, so an unreachable database or a rejected
password is named as such instead of "exit code 1". An unrecognized crash keeps
the raw detail — a confident wrong explanation would be worse than none.

Environment variables are encrypted at rest and injected at build and run time.
Restart the app for changes to take effect.

### As an administrator

Administrators do not deploy. Their navigation has no GitHub connection and no
deploy flow at all — four screens instead:

- **Overview** — activity, build success rate, framework and build-method mix,
  busiest accounts, and anything needing attention.
- **Students** — every account, its quota, and the block/disable controls.
- **Projects** — every deployment on the platform, with suspend and delete.
- **Infrastructure** — live service checks, what each one does, and what breaks
  without it.

---

## Layout

```
backend/
  app/
    api/          route handlers: apps, deployments, admin, the router's config
    auth/         JWT issuing, hashing, dependencies
    builder/      docker build, buildpacks, compose preparation, registry push
    detection/    pure repository analysis — no network, no database
    github/       OAuth, API client, tarball download
    models/       SQLAlchemy tables
    runtime/      container and stack lifecycle, naming, ports, reconciliation
frontend/
  app/            routes: landing, auth, apps and their builds, admin console
  components/     design system (ui.tsx), charts, feature components
  lib/            typed API client
```

### Notes for whoever works on this next

- **Reconciliation at startup.** Deployment rows outlive the process that wrote
  them. On boot the API checks every supposedly-running deployment against
  Docker and corrects the ones that are not, so the dashboard never claims an
  app is up when it is not. The same sweep fails builds that were in flight
  when the process stopped — otherwise a restart mid-build leaves a row stuck
  on `building` for ever, with no way to retry it.
- **One live deployment per hostname, enforced by the database.** A partial
  unique index (`uq_deployments_live_subdomain`) covers only rows that are
  running. An app's builds all share its hostname, so an outright UNIQUE
  constraint would reject the second one; what must never happen is two of them
  serving that name at once, and that is what the index says.
- **The routing table is never returned empty.** Traefik keeps its previous
  configuration when handed an empty one, so a sentinel route is always
  included. Without it, stopping the last running app leaves its URL pointing
  at a dead container. See `api/internal_routes.py`.
- **External commands run on a worker thread**, not through
  `asyncio.create_subprocess_exec`, which raises `NotImplementedError` on a
  Windows Selector event loop — the loop a server may well be running on.
- **`eager_defaults` is on** for every model. Without it `updated_at` is left
  expired after an UPDATE and reading it while building a response emits SQL
  with no greenlet context.
- **Detection never executes anything.** It reads and parses files. Building
  does run the project's own tooling — inherent to building source — which is
  why builds have a hard timeout and are killed as a process tree.
