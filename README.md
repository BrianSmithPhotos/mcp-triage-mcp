# Planner Triage

A small app for triaging Microsoft Planner's "Message Center Posts" plan, plus ad-hoc AI chat
against Planner, built on top of [aixolotl/microsoft-planner-mcp](https://github.com/aixolotl/microsoft-planner-mcp).

See [PLAN.md](./PLAN.md) for the architecture and triage logic.

## Components

- `planner-mcp` — the unofficial Planner MCP server (third-party, run via Docker, not vendored here)
- `backend/` — Python (uv) FastAPI service: MCP client + OpenRouter orchestration for triage, delete, and chat
- `web/` — Next.js (TypeScript) frontend: Triage, delete, and ad-hoc chat UI

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
"To Be Deleted" fallback bucket — adjust `backend/.env` if your bucket names differ (bucket-name
matching is case-insensitive, so small casing differences don't need an env change).

## Running it

```bash
scripts/start_mac.sh   # starts planner-mcp (Docker), backend (:8001), frontend (:3000)
scripts/stop_mac.sh    # stops all three
```

Logs land in `.run/backend.log` and `.run/web.log` (gitignored); PIDs are tracked there too so
`stop.sh` knows what to kill. For `planner-mcp`'s own logs, use `docker compose logs -f
planner-mcp`.

If you'd rather run each piece by hand (e.g. to watch a log directly in its own terminal):

```bash
docker compose up -d                                          # planner-mcp
(cd backend && uv run uvicorn src.main:app --reload --port 8001)  # backend
(cd web && npm run dev)                                       # frontend
```

Open http://localhost:3000.

The first time the backend calls a Planner tool, it opens a browser window for you to sign in to
Microsoft and consent; the token is then reused for the rest of that backend process's life (it's
in-memory only, so a backend restart means signing in again). Because of this, the backend must
run somewhere with access to a browser on your machine (this is why it's not containerized, unlike
`planner-mcp`).

## Status

Verified end-to-end against a real tenant: triage preview/apply, the delete flow, and ad-hoc chat
have all been run against live Planner data, including a full apply (moved real tasks between
buckets) and a partial delete (removed a subset of tasks from "To Be Deleted"). Classification
runs at `temperature=0` for consistent results across repeated runs. See PLAN.md's "Verified
against the live tenant" section for the bugs found and fixed along the way, and its "Open items"
section for what's still rough (mainly: OAuth token doesn't persist across backend restarts, and
the classification prompt's bucket-specific rules are expected to keep evolving as more
misclassifications turn up).
