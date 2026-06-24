import json

from ..config import settings
from ..mcp_client import get_client
from ..openrouter_client import chat_completion

SYSTEM_PROMPT = """You triage Microsoft Planner tasks for a plan called "Message Center Posts".

Each task is a Microsoft 365 Message Center post that was dropped into the "To Do" bucket. Its
title often starts with a bracketed product tag, e.g. "[Microsoft Teams] ...", naming the
Microsoft 365 service the post is about. That tag is NOT the basis for your decision — it almost
never matches a bucket name. What matters is the actual subject of the post: read the full
description and judge what the post is substantively about (a workflow, a tool, a team, a
project), not which product shipped the feature.

You are given the exact list of other available buckets (columns) in the plan, named
"available_buckets" in the user message. Decide, for each task, which bucket it belongs in:

- Only assign a task to a non-fallback bucket if the post's substance — based on its description,
  not its title's product tag — clearly matches that bucket's specific subject matter. For example,
  a Teams-tagged post whose body describes a change to how Planner tasks sync into Teams belongs
  in a bucket named "Planner", not a "Teams" bucket (which likely doesn't exist).
- Otherwise, assign it to the fallback bucket: "{fallback_bucket}". When in doubt, use the
  fallback bucket — do not invent a topic match that isn't a real, given bucket name, and do not
  match on the title's product tag alone.
- "bucket_name" in your response must be copied verbatim from "available_buckets" — never a bucket
  name that isn't in that list, even if it would be a better fit.
- If a post plausibly fits more than one available bucket, prefer a bucket named "Planner" over
  any other candidate. Planner gets first claim on ambiguous posts.

Bucket-specific guidance below adds extra constraints or extra scope for a few named buckets
ONLY. It does not change how you judge any other bucket — every bucket not named below (e.g.
"Planner", "SharePoint") is still decided purely on whether the post's substance matches that
bucket's own plain subject matter, same as the general rule above. Do not apply the "must relate
to project/task management" language below to buckets other than the ones it names.

Bucket-specific guidance (apply these when the matching bucket is present in "available_buckets"):

- "Copilot": for any post substantively about Microsoft Copilot products themselves — Microsoft
  365 Copilot, Copilot Chat, Copilot agents, the Copilot app experience, Copilot-branded features
  in other apps, etc. A long post describing several aspects of the Copilot app/experience (UI,
  navigation, chat, agents) still belongs here even if, along the way, it mentions an unrelated
  named feature or toggle (e.g. a "Work IQ" toggle inside the Copilot app) — that passing mention
  does not redirect the post elsewhere. Judge the post's main subject, not every term it contains.
- "ProjOps": only for posts about Dynamics 365 Project Operations and project management
  capabilities specifically (resourcing, scheduling, project execution). A post that happens to
  mention "Project Operations" but is really about invoicing, billing, or customer/contact
  management does NOT belong here — send it to the fallback bucket instead. Do NOT confuse this
  with classic Microsoft Project, "Project Online", "Project for the web", or "Project Web App" —
  those are a different, older product line and despite the similar name are NOT Dynamics 365
  Project Operations. Posts about that classic Project product line belong in a bucket named
  "Project" instead (if present), not "ProjOps".
- "Special Projects": catch posts about work or task management more broadly, even when they
  don't mention "Project" or "Planner" by name — e.g. Work IQ, CoWork, Microsoft To Do, or other
  task/work-tracking tools and features.

Every task_id from the input must appear exactly once in your response.
"""


async def _get_plan_and_buckets(client):
    plans = await client.call_tool("list_my_plans", {})
    plans_data = plans.data or []
    plan = next((p for p in plans_data if p.get("title") == settings.message_center_plan_name), None)
    if plan is None:
        raise ValueError(f"Plan '{settings.message_center_plan_name}' not found among your Planner plans")

    buckets_result = await client.call_tool("list_buckets", {"planId": plan["id"]})
    buckets = buckets_result.data or []
    return plan, buckets


def _find_bucket(buckets: list[dict], name: str) -> dict | None:
    return next((b for b in buckets if b.get("name", "").strip().lower() == name.strip().lower()), None)


async def get_triage_preview() -> dict:
    client = await get_client()
    plan, buckets = await _get_plan_and_buckets(client)

    todo_bucket = _find_bucket(buckets, settings.todo_bucket_name)
    if todo_bucket is None:
        raise ValueError(f"Bucket '{settings.todo_bucket_name}' not found in plan '{plan['title']}'")

    other_bucket_names = [b["name"] for b in buckets if b["id"] != todo_bucket["id"]]
    if not any(n.strip().lower() == settings.fallback_bucket_name.strip().lower() for n in other_bucket_names):
        other_bucket_names.append(settings.fallback_bucket_name)

    tasks_result = await client.call_tool(
        "list_tasks",
        {"planId": plan["id"], "filter": f"bucketId eq '{todo_bucket['id']}'"},
    )
    tasks = tasks_result.data or []

    if not tasks:
        return {"plan": plan["title"], "todo_bucket": todo_bucket["name"], "decisions": []}

    task_payload = []
    for task in tasks:
        details_result = await client.call_tool("get_task_details", {"taskId": task["id"]})
        description = (details_result.data or {}).get("description", "")
        task_payload.append(
            {
                "task_id": task["id"],
                "title": task.get("title", ""),
                "description": description[:500],
                "etag": task.get("@odata.etag", ""),
            }
        )

    user_prompt = json.dumps(
        {
            "available_buckets": other_bucket_names,
            "fallback_bucket": settings.fallback_bucket_name,
            "tasks": task_payload,
        }
    )

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "triage_decisions",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "string", "enum": [t["task_id"] for t in task_payload]},
                                "bucket_name": {"type": "string", "enum": other_bucket_names},
                                "reason": {"type": "string"},
                            },
                            "required": ["task_id", "bucket_name", "reason"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["decisions"],
                "additionalProperties": False,
            },
        },
    }

    response = await chat_completion(
        model=settings.openrouter_triage_model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(fallback_bucket=settings.fallback_bucket_name),
            },
            {"role": "user", "content": user_prompt},
        ],
        response_format=response_format,
        max_tokens=8000,
        temperature=0,
    )

    content = response["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    decisions = parsed["decisions"]

    bucket_id_by_name = {b["name"]: b["id"] for b in buckets}
    task_by_id = {t["task_id"]: t for t in task_payload}

    enriched = []
    for decision in decisions:
        task = task_by_id.get(decision["task_id"])
        if task is None:
            continue
        enriched.append(
            {
                "task_id": decision["task_id"],
                "title": task["title"],
                "etag": task["etag"],
                "target_bucket_name": decision["bucket_name"],
                "target_bucket_id": bucket_id_by_name.get(decision["bucket_name"]),
                "reason": decision.get("reason", ""),
            }
        )

    return {
        "plan": plan["title"],
        "todo_bucket": todo_bucket["name"],
        "decisions": enriched,
    }


async def apply_triage_decisions(decisions: list[dict]) -> dict:
    """Move each task to its target bucket. `decisions` come straight from the
    preview response the frontend rendered, so they carry the etag captured then;
    update_task retries once server-side if that etag has since gone stale."""
    applied = []
    errors = []
    client = await get_client()
    for decision in decisions:
        task_id = decision["task_id"]
        target_bucket_id = decision.get("target_bucket_id")
        if not target_bucket_id:
            errors.append({"task_id": task_id, "error": "missing target_bucket_id"})
            continue
        try:
            await client.call_tool(
                "update_task",
                {
                    "taskId": task_id,
                    "etag": decision["etag"],
                    "bucketId": target_bucket_id,
                },
            )
            applied.append(task_id)
        except Exception as exc:  # noqa: BLE001 - report per-task failure, keep going
            errors.append({"task_id": task_id, "error": str(exc)})

    return {"applied": applied, "errors": errors}


async def get_deleted_bucket_preview() -> dict:
    """List every task currently in the fallback bucket, for the user to review before
    permanently deleting them. Deleting a Planner bucket does not delete its tasks (they'd
    just be orphaned, pointing at a bucket that no longer exists), so clearing this bucket
    means deleting each task individually and leaving the bucket itself in place."""
    client = await get_client()
    plan, buckets = await _get_plan_and_buckets(client)

    bucket = _find_bucket(buckets, settings.fallback_bucket_name)
    if bucket is None:
        raise ValueError(f"Bucket '{settings.fallback_bucket_name}' not found in plan '{plan['title']}'")

    tasks_result = await client.call_tool(
        "list_tasks",
        {"planId": plan["id"], "filter": f"bucketId eq '{bucket['id']}'"},
    )
    tasks = tasks_result.data or []

    return {
        "plan": plan["title"],
        "bucket": bucket["name"],
        "tasks": [
            {"task_id": t["id"], "title": t.get("title", ""), "etag": t.get("@odata.etag", "")} for t in tasks
        ],
    }


async def delete_bucket_tasks(tasks: list[dict]) -> dict:
    """Permanently delete each given task. `tasks` come straight from the preview response
    the frontend rendered, so the user has already seen what's about to be deleted."""
    deleted = []
    errors = []
    client = await get_client()
    for task in tasks:
        task_id = task["task_id"]
        try:
            await client.call_tool("delete_task", {"taskId": task_id, "etag": task["etag"]})
            deleted.append(task_id)
        except Exception as exc:  # noqa: BLE001 - report per-task failure, keep going
            errors.append({"task_id": task_id, "error": str(exc)})

    return {"deleted": deleted, "errors": errors}
