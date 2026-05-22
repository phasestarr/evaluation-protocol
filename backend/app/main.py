import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import admin, evaluations, auth
from app.services.bootstrap import initialize_runtime_state, session_cleanup_loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_runtime_state()
    cleanup_task = asyncio.create_task(session_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Evaluation Protocol API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(evaluations.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
