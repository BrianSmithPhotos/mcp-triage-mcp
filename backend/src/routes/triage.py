from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.triage_service import (
    apply_triage_decisions,
    delete_bucket_tasks,
    get_deleted_bucket_preview,
    get_triage_preview,
)

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


class TaskRef(BaseModel):
    task_id: str
    title: str
    etag: str


class DeleteRequest(BaseModel):
    tasks: list[TaskRef]


@router.get("/preview")
async def preview():
    try:
        return await get_triage_preview()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/apply")
async def apply(request: ApplyRequest):
    return await apply_triage_decisions([d.model_dump() for d in request.decisions])


@router.get("/deleted-preview")
async def deleted_preview():
    try:
        return await get_deleted_bucket_preview()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/delete")
async def delete(request: DeleteRequest):
    return await delete_bucket_tasks([t.model_dump() for t in request.tasks])
