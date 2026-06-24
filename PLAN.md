# Plan

## Goal

Three features against Microsoft Planner, via [aixolotl/microsoft-planner-mcp](https://github.com/aixolotl/microsoft-planner-mcp):

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
  /            ─┐                   GET  /triage/preview        ──┐                          
  /triage       │  REST, JSON       POST /triage/apply            ├─calls──▶  Microsoft Planner
  /chat        ─┘                   GET  /triage/deleted-preview  │          (via Graph, OAuth)
                                     POST /triage/delete           │                          
                                     POST /chat                  ──┘                          
                                     (MCP client + OpenRouter)
```

- **`planner-mcp`**: the third-party server, run unmodified via `docker compose up` from the
  published image. Not vendored — see root `docker-compose.yml`.
- **`backend/`**: the only thing that talks to `planner-mcp` and to OpenRouter.
  - `src/mcp_client.py` — wraps `fastmcp.Client(url, auth="oauth")` in a single long-lived
    connection, connected lazily on first use. First call opens a browser for Microsoft sign-in;
    the resulting token is reused for the rest of the backend process's life.
  - `src/openrouter_client.py` — thin OpenAI-compatible chat-completions wrapper (supports
    `response_format`, `max_tokens`, `temperature`).
  - `src/services/triage_service.py` — triage and delete logic (see below).
  - `src/services/chat_service.py` — generic tool-calling loop: lists planner-mcp's tools,
    exposes them to the model as OpenAI-style function-calling tools, executes whatever the model
    calls, feeds results back, repeats until the model stops calling tools.
  - `src/routes/triage.py`, `src/routes/chat.py` — FastAPI endpoints the frontend calls.
- **`web/`**: UI only — a dashboard, a triage preview/apply + delete page, and a chat page. Talks
  to the backend over plain `fetch`, no server-side proxying needed since this is a single-user
  local app.

## Triage logic

1. `list_my_plans` → find the plan titled `MESSAGE_CENTER_PLAN_NAME` ("Message Center Posts").
2. `list_buckets` on that plan → find `TODO_BUCKET_NAME` ("To Do", matched case-insensitively);
   collect the other bucket names, plus ensure `FALLBACK_BUCKET_NAME` ("To Be Deleted") is in
   that list.
3. `list_tasks` filtered to that bucket's id (`bucketId eq '...'` — confirmed accurate against
   live data, see below), then `get_task_details` per task for its description (truncated to 500
   chars to keep the prompt size reasonable).
4. One batched call to OpenRouter (`OPENROUTER_TRIAGE_MODEL`, `temperature=0` for deterministic
   results) with all tasks + bucket names, using structured-output JSON
   (`response_format: json_schema`, `strict: true`) with `bucket_name` constrained to an enum of
   the plan's real bucket names — this prevents the model from hallucinating a bucket that doesn't
   exist or wrapping its answer in markdown fences.
5. **Preview** (`GET /triage/preview`) returns the decisions (task title, target bucket, reason,
   captured etag) without changing anything in Planner.
6. **Apply** (`POST /triage/apply`) takes the decisions the UI showed (so the user has seen them)
   and calls `update_task` per task with `bucketId` set to the target. `update_task` retries once
   server-side on a stale etag, so no extra round-trip is needed between preview and apply unless
   the user waits a long time between the two.
7. Tasks whose model-chosen bucket name doesn't match any real bucket are flagged in the UI
   ("bucket not found") instead of silently applied.

No `delete_task` calls anywhere in this flow.

### Classification prompt rules (`SYSTEM_PROMPT` in `triage_service.py`)

General rules, apply to every bucket:
- Judge by the post's description/substance, not its title's bracketed product tag (e.g.
  `[Microsoft Teams] ...` is not evidence the post belongs in a "Teams" bucket).
- When in doubt, use the fallback bucket rather than inventing a topic match.
- If a post plausibly fits more than one bucket, "Planner" wins ties.

Bucket-specific guidance, scoped to only the bucket it names (does not leak into how other
buckets are judged — an earlier version of this prompt caused the model to incorrectly apply
"must relate to project/task management" everywhere, mis-classifying an unrelated Copilot post):
- **Copilot**: any post substantively about Microsoft Copilot products themselves (M365 Copilot,
  Copilot Chat, Copilot agents, etc.), even if it also mentions an unrelated feature/toggle in
  passing (e.g. a post about the Copilot app's UI overhaul that happens to mention a "Work IQ"
  toggle still belongs in Copilot, not Special Projects).
- **ProjOps**: only Dynamics 365 Project Operations / project-management capabilities
  (resourcing, scheduling, execution) — not invoicing/billing/customer content even if it mentions
  "Project Operations". Also explicitly NOT classic Microsoft Project / "Project Online" /
  "Project for the web" / "Project Web App" — that product line, despite the similar name, is
  unrelated to Dynamics 365 Project Operations and belongs in "Project" instead.
- **Special Projects**: catches work/task-management posts that don't mention "Project" or
  "Planner" by name — e.g. Work IQ, CoWork, Microsoft To Do.

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
the delete button is enabled, since this action is irreversible. Verified live: deleting a subset
of tasks from "To Be Deleted" worked correctly.

## Verified against the live tenant

End-to-end testing against the real "Message Center Posts" plan surfaced and fixed several real
bugs along the way (not hypothetical — each one reproduced against live data before being fixed):

- **Tool argument casing**: the upstream README documents snake_case args (`plan_id`,
  `bucket_id`, `task_id`), but the actual tool schemas use camelCase (`planId`, `bucketId`,
  `taskId`, `checklistItems`, `etagDetails`, etc.) — confirmed via `client.list_tools()`.
- **Classification JSON reliability**: fixed via structured-output mode with an enum constraint
  on `bucket_name` (see above) — also fixed an `Expecting value: line 1 column 1` 500 that was
  really a `json.JSONDecodeError` being mis-caught as "plan/bucket not found".
- **OAuth token reuse**: switched from a fresh `fastmcp.Client` per request (re-authenticating
  every time) to one long-lived client for the process's life.
- **Real bucket name**: this tenant's source bucket is "To do" (lowercase "do"), not "To Do" —
  bucket-name matching is now case-insensitive everywhere.
- **`list_tasks` bucket filter accuracy**: a chat session once self-reported the `bucketId eq
  '...'` filter "doesn't work" and worked around it by fetching all tasks and counting manually.
  Directly tested the filter against all 7 real buckets afterward and it matched manual counts
  exactly every time — the filter itself is reliable; that one instance was likely the chat model
  using a stale/incorrect bucket ID rather than an actual API bug.
- **Classification determinism**: the triage call ran at default sampling temperature, so the
  same task could classify differently between runs — this surfaced as an apparently-flaky fix
  (a misclassified task appeared fixed, then wasn't, then was again) until traced to
  non-determinism rather than the prompt itself. Pinned to `temperature=0`; verified 3 repeated
  runs against the same live task agree every time.
- **Chat counting reliability**: chat models (tried Sonnet, Haiku 4.5, gpt-4o-mini) cannot reliably
  count items in a JSON array they receive as a raw tool result — confirmed reproducibly: 3 runs
  against a stable, known-28-item bucket returned wrong, non-deterministic counts (32/31/30, then
  44/51/40 on a cheaper model) even with an explicit "count precisely" system-prompt instruction.
  This isn't fixable by prompting or by picking a smarter (more expensive) model. Fixed
  architecturally instead, in `chat_service.py`: any list-shaped tool result is wrapped as
  `{"count": N, "items": [...]}` before being sent to the model, with an instruction to read
  `count` directly rather than counting `items` by hand. Verified 3/3 correct after the fix, with
  the cheapest model (`gpt-4o-mini`).
- **Classification prompt iteration** (see rules above): caught and fixed three real
  misclassifications during live retesting — title-tag bias (Teams-tagged posts auto-assigned to
  a nonexistent "Teams" bucket), ProjOps/Project confusion (Project Online vs. Dynamics 365
  Project Operations), and guidance bleed (Copilot post mis-routed to fallback because unrelated
  bucket-specific language leaked into how Copilot was judged).

## Open items

- **OAuth token persistence across restarts**: token is still in-memory only, so a backend
  restart (including `--reload` during dev) forces a fresh browser sign-in. Could wire up a
  file-based `AsyncKeyValue` token store (fastmcp supports this) if recurring restarts become
  annoying.
- **Model choice**: both `OPENROUTER_TRIAGE_MODEL` and `OPENROUTER_CHAT_MODEL` default to
  `openai/gpt-4o-mini` — cheap, and reliable for chat now that counting no longer depends on the
  model itself (see "Chat counting reliability" above). Easily changed via env var if chat quality
  needs to go up for more complex ad-hoc requests beyond simple counts/lookups.
- **Pagination**: not yet handling more than one MCP "page" if a plan has very large numbers of
  buckets/tasks (this tenant's data, ~100-130 tasks across 8 buckets, has always come back in one
  `list_tasks` call so far).
- **Classification rules will keep evolving**: the bucket-specific guidance section in
  `SYSTEM_PROMPT` is the place to add more rules as more misclassifications turn up — this is
  expected to be an ongoing, iterative process rather than a one-time fix.

## What's NOT built yet

- UI polish beyond a functional preview table, delete confirmation flow, and chat thread.
- Persistent OAuth token storage across backend restarts.
