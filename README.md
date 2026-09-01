# DeployForge

Connect a GitHub repository and DeployForge detects how it should be built —
Docker or a buildpack, and which framework.

## Requirements

- PostgreSQL **15+** (15 is the minimum, older versions fail the migration)
- Python **3.12+**
- Node.js **20+**

## 1. Database

**Linux / macOS**

```bash
sudo -u postgres psql -c "CREATE ROLE deployforge LOGIN PASSWORD 'deployforge';"
sudo -u postgres psql -c "CREATE DATABASE deployforge OWNER deployforge;"
```

**Windows (PowerShell)** — enter the password you set when installing PostgreSQL:

```powershell
psql -U postgres -c "CREATE ROLE deployforge LOGIN PASSWORD 'deployforge';"
psql -U postgres -c "CREATE DATABASE deployforge OWNER deployforge;"
```

## 2. Backend dependencies

**Linux / macOS**

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 3. Backend environment

**Linux / macOS**

```bash
cp .env.example .env
./.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
./.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Windows (PowerShell)**

```powershell
Copy-Item .env.example .env
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Open `backend/.env` and set:

```
DATABASE_URL=postgresql+asyncpg://deployforge:deployforge@localhost:5432/deployforge
JWT_SECRET=<first command's output>
TOKEN_ENCRYPTION_KEY=<second command's output>
GITHUB_CLIENT_ID=<from step 4>
GITHUB_CLIENT_SECRET=<from step 4>
GITHUB_CALLBACK_URL=http://localhost:8000/github/callback
GITHUB_OAUTH_SCOPES=repo
FRONTEND_ORIGIN=http://localhost:3000
APP_ENV=development
```

`.env` is gitignored. Never commit it.

## 4. GitHub OAuth App

**GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**

| Field | Value |
|---|---|
| Application name | `DeployForge (local)` |
| Homepage URL | `http://localhost:3000` |
| Redirect URI | `http://localhost:8000/github/callback` |
| Allow wildcard matching | off |
| Enable Device Flow | off |
| Expire user access tokens | **off** |

Then **Generate a new client secret** (shown only once) and put the client id
and secret in `.env`.

The Redirect URI must match `GITHUB_CALLBACK_URL` exactly — port **8000**, not
3000.

## 5. Migrations

From `backend/`:

```bash
./.venv/bin/alembic upgrade head          # Linux / macOS
.venv\Scripts\alembic upgrade head        # Windows
```

## 6. Admin account

From `backend/`:

```bash
./.venv/bin/python -m scripts.create_admin you@example.com     # Linux / macOS
.venv\Scripts\python -m scripts.create_admin you@example.com   # Windows
```

Prompts for a password. Signup through the UI always creates a normal user;
this is the only way to make an admin.

## 7. Frontend

```bash
cd ../frontend
npm install
cp .env.example .env.local              # Linux / macOS
Copy-Item .env.example .env.local       # Windows
```

## 8. Run

Two terminals.

**Backend** — from `backend/`:

```bash
./.venv/bin/uvicorn app.main:app --reload --port 8000       # Linux / macOS
.venv\Scripts\uvicorn app.main:app --reload --port 8000     # Windows
```

**Frontend** — from `frontend/`:

```bash
npm run dev
```

Open <http://localhost:3000>.

Check the backend: <http://localhost:8000/health> should report
`"status":"ok"` and `"database":"ok"`.

## 9. Tests

From the repository root:

```bash
backend/.venv/bin/python -m pytest backend/tests/         # Linux / macOS
backend\.venv\Scripts\python -m pytest backend\tests\     # Windows
```

Tests run against your real database inside transactions that roll back, so
they leave no rows behind. GitHub is mocked; nothing contacts github.com.

---

## Using it

Sign up → **Start new deployment** → **Authorize GitHub** → pick a repository →
pick what inside it to deploy → see the result.

For a monorepo, the target picker lists each top-level directory with what was
detected in it, so you choose whether to deploy `frontend/`, `backend/`, or the
whole repository.

Admins see every account and their deployments on `/dashboard`. Normal users see
their own.
