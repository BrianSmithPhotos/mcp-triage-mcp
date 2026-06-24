from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import chat, triage

app = FastAPI(title="Planner Triage Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(triage.router)
app.include_router(chat.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
