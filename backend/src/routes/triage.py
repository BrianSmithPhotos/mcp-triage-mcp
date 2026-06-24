from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.triage_service import apply_triage_decisions, get_triage_preview

router = APIRouter(prefix="/triage", tags=["triage"])


class Decision(BaseModel):
    task_id: str
    title: str
    etag: str
    target_bucket_name: str
    target_bucket_id: str | None
    reason: str = ""


class ApplyRequest(BaseModel):
    decisions: list[Decision]


@router.get("/preview")
async def preview():
    try:
        return await get_triage_preview()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/apply")
async def apply(request: ApplyRequest):
    return await apply_triage_decisions([d.model_dump() for d in request.decisions])
