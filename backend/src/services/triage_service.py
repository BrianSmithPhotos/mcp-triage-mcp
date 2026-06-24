import json

from ..config import settings
from ..mcp_client import planner_client
from ..openrouter_client import chat_completion

SYSTEM_PROMPT = """You triage Microsoft Planner tasks for a plan called "Message Center Posts".

Each task is a Microsoft 365 Message Center post that was dropped into the "To Do" bucket.
You are given the other available buckets (columns) in the plan. Decide, for each task, which
bucket it belongs in:

- If the task's title/description clearly matches the subject matter of one of the other bucket
  names (e.g. a bucket called "Teams" and a task about a Teams feature change), assign it to that
  bucket.
- Otherwise, assign it to the fallback bucket: "{fallback_bucket}".

Respond with strict JSON only, no prose, in this shape:
{{"decisions": [{{"task_id": "...", "bucket_name": "...", "reason": "short reason"}}]}}

Every task_id from the input must appear exactly once in "decisions". "bucket_name" must be one of
the provided bucket names exactly as given (including the fallback bucket name).
"""


async def _get_plan_and_buckets(client):
    plans = await client.call_tool("list_my_plans", {})
    plans_data = plans.data or []
    plan = next((p for p in plans_data if p.get("title") == settings.message_center_plan_name), None)
    if plan is None:
        raise ValueError(f"Plan '{settings.message_center_plan_name}' not found among your Planner plans")

    buckets_result = await client.call_tool("list_buckets", {"plan_id": plan["id"]})
    buckets = buckets_result.data or []
    return plan, buckets


async def get_triage_preview() -> dict:
    async with planner_client() as client:
        plan, buckets = await _get_plan_and_buckets(client)

        todo_bucket = next((b for b in buckets if b.get("name") == settings.todo_bucket_name), None)
        if todo_bucket is None:
            raise ValueError(f"Bucket '{settings.todo_bucket_name}' not found in plan '{plan['title']}'")

        other_bucket_names = [b["name"] for b in buckets if b["id"] != todo_bucket["id"]]
        if settings.fallback_bucket_name not in other_bucket_names:
            other_bucket_names.append(settings.fallback_bucket_name)

        tasks_result = await client.call_tool(
            "list_tasks",
            {"plan_id": plan["id"], "filter": f"bucketId eq '{todo_bucket['id']}'"},
        )
        tasks = tasks_result.data or []

        if not tasks:
            return {"plan": plan["title"], "todo_bucket": todo_bucket["name"], "decisions": []}

        task_payload = []
        for task in tasks:
            details_result = await client.call_tool("get_task_details", {"task_id": task["id"]})
            description = (details_result.data or {}).get("description", "")
            task_payload.append(
                {
                    "task_id": task["id"],
                    "title": task.get("title", ""),
                    "description": description,
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

        response = await chat_completion(
            model=settings.openrouter_triage_model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT.format(fallback_bucket=settings.fallback_bucket_name),
                },
                {"role": "user", "content": user_prompt},
            ],
            tool_choice=None,
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
    async with planner_client() as client:
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
                        "task_id": task_id,
                        "etag": decision["etag"],
                        "bucket_id": target_bucket_id,
                    },
                )
                applied.append(task_id)
            except Exception as exc:  # noqa: BLE001 - report per-task failure, keep going
                errors.append({"task_id": task_id, "error": str(exc)})

    return {"applied": applied, "errors": errors}
