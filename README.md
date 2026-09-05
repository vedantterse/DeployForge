# DeployForge

Connect a GitHub repository. DeployForge works out how it should be built,
builds it, stores the image in a registry, and runs it in an isolated
container behind its own URL.

Built for a shared machine — a class of students deploying to one server — so
quotas, per-app resource limits and administrator control are part of the
design rather than an afterthought.

---

## How it works

```
GitHub repo ──> download ──> detect ──> build ──> registry ──> run ──> URL
                (tarball)   (read      (Docker    (image     (container)
                             only)      or         stored)
                                        buildpack)
```

1. **Connect** — the student authorizes a GitHub OAuth App. The access token is
   Fernet-encrypted before it is stored and never reaches the browser.
2. **Detect** — the repository is downloaded as a tarball and *read*, never
   executed. A Dockerfile means Docker; otherwise the framework is identified
   from `package.json`, `requirements.txt`, `go.mod` and friends. A monorepo
   gets one candidate per top-level directory, and the student chooses.
3. **Build** — a Dockerfile is built with `docker build`; anything else with
   Cloud Native Buildpacks (`pack`). The decision is made against the files
   actually being built, not a stale detection row.
4. **Store** — the image is pushed to a local registry, so what ran is a
   retrievable artifact rather than a tag on one machine.
5. **Run** — the image runs in a container on a private network, with no host
   port published. A reverse proxy is the only way in.

### Routing

Every deployment gets a hostname: `<repo>-<id6>.localhost`. Browsers resolve
any `*.localhost` name to the loopback address with no DNS or hosts-file entry,
which is what makes per-app URLs work on a laptop.

Traefik polls `GET /internal/traefik/config` every few seconds and rebuilds its
routing table from the `deployments` table. That makes the database the single
source of truth: a stopped app leaves the routing table within one poll, and no
proxy config is ever written to disk or reloaded by hand.

It also means the proxy needs **no access to the Docker socket**. Socket access
is root-equivalent on the host, and granting it to an internet-facing process
to save writing one endpoint would be a poor trade.

### Isolation

Each app container gets a memory cap, a CPU cap, a PID limit and
`--security-opt no-new-privileges`, and publishes no host port. Accounts have a
quota for how many apps they may run at once. Administrators can suspend an
app, which stops it *and* prevents the owner from simply starting it again.

---

## Requirements

- **Docker** — required. Runs PostgreSQL, the registry, the router, and every
  deployed app.
- **Python 3.12+**, **Node.js 20+**
- **`pack` CLI 0.40+** — optional. Only needed to deploy repositories that have
  no Dockerfile. Everything else works without it.

`pack` older than 0.40 uses a Docker API version modern daemons reject. Check
with `pack version`; install from <https://buildpacks.io/docs/install-pack/>.

---

## 1. Infrastructure

Three containers: the database, the image registry, and the router.

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
PostgreSQL already running on the host. The token in the Traefik command must
match `TRAEFIK_PROVIDER_TOKEN` in `backend/.env`.

Traefik reaches the backend at `host.docker.internal`, which Docker Desktop
provides. On Linux, add `--add-host=host.docker.internal:host-gateway`.

## 2. Backend

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

On Linux/macOS use `.venv/bin/pip`.

## 3. Configuration

```bash
cd backend && cp .env.example .env
```

Generate the two secrets:

```bash
cd backend && .venv/Scripts/python -c "import secrets; from cryptography.fernet import Fernet; print('JWT_SECRET=' + secrets.token_hex(32)); print('TOKEN_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Then edit `backend/.env`:

```
DATABASE_URL=postgresql+asyncpg://deployforge:deployforge@localhost:5433/deployforge
JWT_SECRET=<from above>
TOKEN_ENCRYPTION_KEY=<from above>
GITHUB_CLIENT_ID=<from step 4>
GITHUB_CLIENT_SECRET=<from step 4>
TRAEFIK_PROVIDER_TOKEN=<same value as in the Traefik command>
```

> **Never re-copy `.env.example` over a working `.env`.** It resets
> `DATABASE_URL` to port 5432, and replacing `TOKEN_ENCRYPTION_KEY` makes every
> stored GitHub token permanently undecryptable. Edit the lines you need.

The build and runtime settings — resource limits, quotas, the registry host —
all have working defaults. See the comments in `.env.example`.

## 4. GitHub OAuth App

**GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**

| Field | Value |
|---|---|
| Application name | `DeployForge (local)` |
| Homepage URL | `http://localhost:3000` |
| Authorization callback URL | `http://localhost:8000/github/callback` |

The callback must match `GITHUB_CALLBACK_URL` exactly — port **8000**, not
3000. Generate a client secret; it is shown once and can only ever be replaced,
never retrieved.

## 5. Migrations

```bash
cd backend && .venv/Scripts/alembic upgrade head
```

## 6. Admin account

```bash
cd backend && .venv/Scripts/python -m scripts.create_admin you@example.com
```

Signup through the UI always creates a normal user. This is the only way to
make an admin.

## 7. Frontend

```bash
cd frontend && npm install && cp .env.example .env.local
```

## 8. Run

Two terminals.

```bash
cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Open <http://localhost:3000>. <http://localhost:8000/health> should report
`"status":"ok"` and `"database":"ok"`; the admin console shows whether Docker,
the registry, the router and buildpacks are all reachable.

`.env` changes need a backend **restart** — uvicorn's reloader only watches
`.py` files, and settings are cached at import.

## 9. Tests

```bash
backend/.venv/Scripts/python -m pytest backend/tests/
```

Tests run against the real database inside transactions that roll back, so they
leave no rows behind. Docker and GitHub are stubbed; nothing is built, run or
fetched.

---

## Using it

Sign up → **Deploy new app** → **Authorize GitHub** → pick a repository → pick
what inside it to deploy → **Build and deploy** → **Start**.

The build runs in the background and its log streams on the deployment page.
The first buildpack build on a machine downloads a ~4.7 GB builder image, so it
takes a while; Dockerfile builds have no such cost.

Two logs are kept apart on purpose:

- the **build log** says why no image could be produced;
- the **runtime log** says why the image that was produced will not stay up.

Admins get two extra screens: **Accounts** (everyone, their quota, enable and
disable) and **All apps** (every deployment, with suspend and delete).

---

## Layout

```
backend/
  app/
    api/          route handlers, including the router's config endpoint
    auth/         JWT issuing, hashing, dependencies
    builder/      docker build + buildpack build, orchestration, registry push
    detection/    pure repository analysis — no network, no database
    github/       OAuth, API client, tarball download
    models/       SQLAlchemy tables
    runtime/      container lifecycle, naming, port choice, reconciliation
frontend/
  app/            routes: landing, auth, dashboard, deployment detail, admin
  components/     design system (ui.tsx) and feature components
  lib/            typed API client
```

### Notes

- **Reconciliation at startup.** Deployment rows outlive the process that wrote
  them — Docker restarts, machines reboot. On boot the API checks every
  supposedly-running deployment against Docker and corrects the ones that are
  not, so the dashboard never claims an app is up when it is not.
- **Compose is refused, clearly.** A `docker-compose.yml` describes several
  services and their wiring; there is no single image to produce. DeployForge
  says so instead of building something that is not what the file describes.
- **Detection never executes anything.** It reads and parses files. Building
  does run the project's own tooling — that is inherent to building source, and
  is why builds have a hard timeout and run in their own process group.
