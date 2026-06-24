# Planner Triage

A small app for triaging Microsoft Planner's "Message Center Posts" plan, plus ad-hoc AI chat
against Planner, built on top of [aixolotl/microsoft-planner-mcp](https://github.com/aixolotl/microsoft-planner-mcp).

See [PLAN.md](./PLAN.md) for the architecture and triage logic.

## Components

- `planner-mcp` — the unofficial Planner MCP server (third-party, run via Docker, not vendored here)
- `backend/` — Python (uv) FastAPI service: MCP client + OpenRouter orchestration for triage and chat
- `web/` — Next.js (TypeScript) frontend: Triage button and ad-hoc chat UI

## One-time setup

### 1. Azure Entra ID app registration

The Planner MCP server needs its own Azure app registration to call Microsoft Graph on your
behalf. Follow ["Azure Entra ID Setup"](https://github.com/aixolotl/microsoft-planner-mcp#azure-entra-id-setup)
in its README:

1. Register an app in Entra ID, redirect URI `http://localhost:8000/auth/callback`.
2. Add delegated Graph permissions: `Tasks.ReadWrite`, `User.Read`, `User.ReadBasic.All`. Grant
   admin consent.
3. Expose an API scope named `mcp-access`.
4. Set `requestedAccessTokenVersion` to `2` in the app manifest.
5. Create a client secret.
6. Note the **Application (client) ID**, **Directory (tenant) ID**, and **client secret value**.

### 2. OpenRouter API key

Create a key at https://openrouter.ai/keys.

### 3. Fill in env files

```bash
cp .env.example .env                 # planner-mcp container config
cp backend/.env.example backend/.env # OpenRouter + plan/bucket names
cp web/.env.example web/.env         # backend URL for the browser
```

Fill in `.env` (root) with the Azure values from step 1, and `backend/.env` with your OpenRouter
key. Defaults assume your plan is called "Message Center Posts" with a "To Do" bucket and a
"To Be Deleted" fallback bucket — adjust `backend/.env` if your bucket names differ.

## Running it

```bash
# 1. Planner MCP server
docker compose up -d

# 2. Backend (separate terminal)
cd backend
uv run uvicorn src.main:app --reload --port 8001

# 3. Frontend (separate terminal)
cd web
npm run dev
```

Open http://localhost:3000.

The first time the backend calls a Planner tool, it opens a browser window for you to sign in to
Microsoft and consent; the token is then cached locally so you won't see that again until it
expires. Because of this, the backend must run somewhere with access to a browser on your machine
(this is why it's not containerized, unlike `planner-mcp`).

## Status

Scaffolding only — not yet run end-to-end against a real Planner tenant. Once Azure credentials
are in place, expect to debug exact field names/shapes coming back from the MCP tools (e.g.
whether `list_buckets`/`list_tasks` results key fields as `name`/`title` and where the etag lives)
against this code.
