# Plan

## Goal

Two features against Microsoft Planner, via [aixolotl/microsoft-planner-mcp](https://github.com/aixolotl/microsoft-planner-mcp):

1. **Triage button** — for the plan "Message Center Posts", look at every task in the "To Do"
   bucket and decide which bucket it actually belongs in. Most go to "To Be Deleted"; any that
   clearly match another bucket's name/topic go there instead. Triage itself only moves tasks
   between buckets, never deletes.
2. **Delete button** — permanently delete every task currently sitting in "To Be Deleted".
3. **Ad-hoc chat** — a general chat interface that can call any Planner MCP tool on request
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

## Delete logic

`GET /triage/deleted-preview` lists every task currently in the fallback bucket (just title +
etag, for the user to review). `POST /triage/delete` calls `delete_task` on each one individually
and leaves the bucket itself in place.

This is individual deletes rather than delete-and-recreate-the-bucket because **deleting a
Planner bucket via the Graph API does not cascade-delete its tasks** — confirmed by creating a
throwaway bucket + task and deleting the bucket: the task survived, still pointing at the
now-nonexistent `bucketId` (orphaned). The Planner web UI likely deletes tasks individually before
removing a bucket, which is why deleting a bucket from the UI "just works" while doing so through
this raw Graph endpoint would not. The frontend requires an explicit checkbox confirmation before
the delete button is enabled, since this action is irreversible.

## Verified against the live tenant (2026-06-24)

Ran `/triage/preview` and `/chat` end-to-end against the real "Message Center Posts" plan.
Two real bugs surfaced and were fixed:

- **Tool argument casing**: the README documents snake_case args (`plan_id`, `bucket_id`,
  `task_id`), but this server version's actual tool schemas use camelCase (`planId`, `bucketId`,
  `taskId`, `checklistItems`, `etagDetails`, etc.) — confirmed via `client.list_tools()`. All
  `call_tool(...)` calls in `triage_service.py`/`chat_service.py` now use the live schema's names.
- **Classification JSON reliability**: the model sometimes wrapped its answer in markdown fences
  or hallucinated a bucket name not in the real list (e.g. invented "Teams" when no such bucket
  exists). Fixed by switching to OpenRouter's structured-output mode
  (`response_format: json_schema`, `strict: true`) with `bucket_name` constrained to an enum of
  the plan's actual bucket names — this also fixed an `Expecting value: line 1 column 1` 500 that
  was really a `json.JSONDecodeError` being mis-caught as "plan/bucket not found".
- **OAuth token reuse**: originally opened a fresh `fastmcp.Client` (and thus a fresh browser
  OAuth handshake) on every backend request. Replaced with a single long-lived `Client`, connected
  lazily on first use and reused for the rest of the process's life — confirmed by log: one
  "OAuth authorization URL" entry per process start, not per request.
- **Confirmed live shapes**: `list_buckets` → `{id, "@odata.etag", name, orderHint, planId}`;
  `list_tasks` → includes `title`, `bucketId`, `"@odata.etag"`, `percentComplete`, etc.;
  `get_task_details` → `{id, description, checklist, references, ...}`. These matched the
  original assumptions exactly.
- **Real bucket name**: this tenant's source bucket is actually named **"To do"** (lowercase
  "do"), not "To Do" as initially assumed. Bucket-name matching in `triage_service.py` is now
  case-insensitive so small naming variations like this don't require an env var change.
- **Classification quality**: first run with a loose prompt mis-routed 2 posts to "Copilot" based
  on their title's bracketed product tag (e.g. "[Microsoft Teams] ...") rather than their actual
  content. Per user feedback, the prompt now explicitly tells the model the title's product tag is
  not the basis for the decision — only the description's substance is. Re-run: all 27 posts
  correctly fell back to "To Be Deleted" with zero unmatched buckets. User has more bucket-specific
  rules to add later (e.g. for "ProjOps") once this baseline is settled.

## Open items

- **OAuth token persistence across restarts**: token is still in-memory only, so a backend
  restart (including `--reload` during dev) forces a fresh browser sign-in. Could wire up a
  file-based `AsyncKeyValue` token store (fastmcp supports this) if recurring restarts become
  annoying.
- **Apply not yet exercised live**: `/triage/preview` and `/chat` were tested against the real
  tenant; `/triage/apply` (which actually calls `update_task` to move tasks) was deliberately not
  triggered outside the UI, since it mutates the real Planner board — first real run should happen
  via the Triage page's "Apply moves" button after reviewing a preview.
- **Model choice**: `OPENROUTER_TRIAGE_MODEL=openai/gpt-4o-mini` (cheap, high-volume
  classification) and `OPENROUTER_CHAT_MODEL=anthropic/claude-sonnet-4.6` (chat) are defaults,
  easily changed via env var.
- **Pagination**: not yet handling more than one MCP "page" if a plan has very large numbers of
  buckets/tasks (this tenant's 27-28 tasks all came back in one `list_tasks` call).

## What's NOT built yet

- UI polish beyond a functional preview table and chat thread.
- Bucket-specific classification rules (e.g. for "ProjOps") — pending more detailed guidance.
