import httpx

from .config import settings


async def chat_completion(
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    response_format: dict | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict:
    payload: dict = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice
    if response_format:
        payload["response_format"] = response_format
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json=payload,
        )
        response.raise_for_status()
        return response.json()
