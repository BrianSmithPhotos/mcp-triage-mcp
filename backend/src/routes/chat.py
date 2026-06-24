from fastapi import APIRouter
from pydantic import BaseModel

from ..services.chat_service import run_chat

router = APIRouter(prefix="/chat", tags=["chat"])


class Message(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    messages: list[Message]


@router.post("")
async def chat(request: ChatRequest):
    history = [m.model_dump(exclude_none=True) for m in request.messages]
    new_messages = await run_chat(history)
    return {"messages": new_messages}
