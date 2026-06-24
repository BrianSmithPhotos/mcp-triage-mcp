# Plan

## Goal

Two features against Microsoft Planner, via [aixolotl/microsoft-planner-mcp](https://github.com/aixolotl/microsoft-planner-mcp):

1. **Triage button** — for the plan "Message Center Posts", look at every task in the "To Do"
   bucket and decide which bucket it actually belongs in. Most go to "To Be Deleted"; any that
   clearly match another bucket's name/topic go there instead. No deletions at this stage —
   triage only moves tasks between buckets.
2. **Ad-hoc chat** — a general chat interface that can call any Planner MCP tool on request
   (create/read/update/delete tasks, buckets, plans) for one-off work.

## Architecture

```
web/ (Next.js, TypeScript)        backend/ (Python, uv, FastAPI)        planner-mcp (Docker)
  /            ─┐                   GET  /triage/preview   ──calls──▶    Microsoft Planner
  /triage       │  REST, JSON       POST /triage/apply                  (via Graph, OAuth)
  /chat        ─┘                   POST /chat
                                     (MCP client + OpenRouter)
```

- **`planner-mcp`**: the third-party server, run unmodified via `docker compose up` from the
  published image. Not vendored — see root `docker-compose.yml`.
- **`backend/`**: the only thing that talks to `planner-mcp` and to OpenRouter.
  - `src/mcp_client.py` — wraps `fastmcp.Client(url, auth="oauth")`. First call opens a browser
    for Microsoft sign-in; FastMCP caches the resulting token locally so later calls are silent.
  - `src/openrouter_client.py` — thin OpenAI-compatible chat-completions wrapper.
  - `src/services/triage_service.py` — triage logic (see below).
  - `src/services/chat_service.py` — generic tool-calling loop: lists planner-mcp's tools,
    exposes them to the model as OpenAI-style function-calling tools, executes whatever the model
    calls, feeds results back, repeats until the model stops calling tools.
  - `src/routes/triage.py`, `src/routes/chat.py` — FastAPI endpoints the frontend calls.
- **`web/`**: UI only — a dashboard, a triage preview/apply page, and a chat page. Talks to the
  backend over plain `fetch`, no server-side proxying needed since this is a single-user local app.

## Triage logic

1. `list_my_plans` → find the plan titled `MESSAGE_CENTER_PLAN_NAME` ("Message Center Posts").
2. `list_buckets` on that plan → find `TODO_BUCKET_NAME` ("To Do"); collect the other bucket
   names, plus ensure `FALLBACK_BUCKET_NAME` ("To Be Deleted") is in that list.
3. `list_tasks` filtered to that bucket's id, then `get_task_details` per task for its description.
4. One batched call to OpenRouter (`OPENROUTER_TRIAGE_MODEL`) with all tasks + bucket names,
   asking for strict JSON: `{task_id, bucket_name, reason}` per task. The prompt instructs the
   model to only pick a non-fallback bucket when the task content clearly matches that bucket's
   subject, defaulting to the fallback bucket otherwise.
5. **Preview** (`GET /triage/preview`) returns the decisions (task title, target bucket, reason,
   captured etag) without changing anything in Planner.
6. **Apply** (`POST /triage/apply`) takes the decisions the UI showed (so the user has seen them)
   and calls `update_task` per task with `bucket_id` set to the target. `update_task` retries once
   server-side on a stale etag, so no extra round-trip is needed between preview and apply unless
   the user waits a long time between the two.
7. Tasks whose model-chosen bucket name doesn't match any real bucket are flagged in the UI
   ("bucket not found") instead of silently applied.

No `delete_task` calls anywhere in this flow.

## Open items / assumptions to verify once Azure credentials exist

- **Field names from Graph**: assumed `list_buckets` returns `{id, name}` and `list_tasks`
  returns `{id, title, "@odata.etag", bucketId, ...}` per standard Planner/Graph shapes. Not yet
  confirmed against a live response — likely the first thing to fix once auth is wired up.
- **OAuth flow on the backend**: `fastmcp.Client(auth="oauth")` opens a local browser and a
  callback listener. This needs the backend process to run on a machine with a browser available
  to you — confirmed this is fine since it's a single-user local app, but worth knowing if you
  ever want to deploy the backend somewhere headless.
- **Bucket/plan name matching**: triage matches by *exact* plan/bucket title strings from
  `backend/.env`. If "Message Center Posts" or any bucket gets renamed, update the env vars.
- **Model choice**: `OPENROUTER_TRIAGE_MODEL=openai/gpt-4o-mini` (cheap, high-volume
  classification) and `OPENROUTER_CHAT_MODEL=anthropic/claude-sonnet-4.6` (chat) are defaults,
  easily changed via env var.

## What's NOT built yet

- Real end-to-end test against your tenant (needs your Azure app registration + OpenRouter key).
- Any UI polish beyond a functional preview table and chat thread.
- Handling more than one MCP "round" of pagination if a plan has very large numbers of buckets/tasks.
