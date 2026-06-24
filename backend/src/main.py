from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import mcp_client
from .routes import chat, triage


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await mcp_client.disconnect()


app = FastAPI(title="Planner Triage Backend", lifespan=lifespan)

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
