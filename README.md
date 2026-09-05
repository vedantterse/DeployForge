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

| Found in the target | How it is built | What runs |
|---|---|---|
| `docker-compose.yml` / `compose.yaml` | `docker compose up --build` | **every service in the file** |
| `Dockerfile` | `docker build` | one container |
| Neither | Cloud Native Buildpacks (`pack`) | one container |

Compose wins over a Dockerfile beside it: when a repository has both, the
compose file is the author saying "this app is these services together".

**Monorepos.** A repository with `frontend/` and `backend/` offers both as
separate targets. Each is connected and deployed independently, with its own
URL, environment variables and lifecycle.

**One target, one deployment.** A target that is already connected is marked in
the repository list and cannot be selected again — a monorepo's *other*
directories stay available.

### Routing

Every deployment gets a hostname: `<repo>-<id6>.localhost`. Browsers resolve
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

Administrators have three distinct levers, kept separate because they answer
different problems:

| Lever | Effect |
|---|---|
| **Quota** | how many apps this account may run at once |
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

The build runs in the background and its log streams on the deployment page.
The first buildpack build on a machine downloads a large builder image, so it
takes a while; Dockerfile and Compose builds have no such cost.

Two logs are kept apart on purpose:

- the **build log** says why no image could be produced;
- the **runtime log** says why the app that was built will not stay up. For a
  compose stack it covers every service, because the reason the web service is
  failing is usually printed by the database next to it.

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
    api/          route handlers, including the router's config endpoint
    auth/         JWT issuing, hashing, dependencies
    builder/      docker build, buildpacks, compose preparation, registry push
    detection/    pure repository analysis — no network, no database
    github/       OAuth, API client, tarball download
    models/       SQLAlchemy tables
    runtime/      container and stack lifecycle, naming, ports, reconciliation
frontend/
  app/            routes: landing, auth, student dashboard, admin console
  components/     design system (ui.tsx), charts, feature components
  lib/            typed API client
```

### Notes for whoever works on this next

- **Reconciliation at startup.** Deployment rows outlive the process that wrote
  them. On boot the API checks every supposedly-running deployment against
  Docker and corrects the ones that are not, so the dashboard never claims an
  app is up when it is not.
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
