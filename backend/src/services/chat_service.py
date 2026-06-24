import json

from ..config import settings
from ..mcp_client import get_client
from ..openrouter_client import chat_completion

SYSTEM_PROMPT = """You are an assistant that helps the user manage Microsoft Planner via tool
calls. Use the available tools to look up plans, buckets, and tasks, and to create, update, or
delete them as the user asks. Confirm destructive actions (delete_task, delete_bucket,
delete_plan) by clearly stating what you are about to delete before calling the tool, unless the
user has already explicitly confirmed in this conversation."""

MAX_TOOL_ROUNDS = 8


def _mcp_tool_to_openai_schema(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


async def run_chat(history: list[dict]) -> list[dict]:
    """Run one assistant turn, including any tool-call round trips. Returns the
    new messages to append to the conversation (one or more assistant/tool messages)."""
    client = await get_client()
    mcp_tools = await client.list_tools()
    tools = [_mcp_tool_to_openai_schema(t) for t in mcp_tools]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    new_messages: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = await chat_completion(
            model=settings.openrouter_chat_model,
            messages=messages,
            tools=tools,
        )
        message = response["choices"][0]["message"]
        messages.append(message)
        new_messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            break

        for call in tool_calls:
            args = json.loads(call["function"]["arguments"] or "{}")
            result = await client.call_tool(call["function"]["name"], args)
            tool_message = {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result.data),
            }
            messages.append(tool_message)
            new_messages.append(tool_message)

    return new_messages
