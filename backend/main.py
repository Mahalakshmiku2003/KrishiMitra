from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.db import models  # noqa: F401
from backend.db.database import Base, engine
from backend.routes.whatsapp import router as whatsapp_router
from backend.scheduler import start_scheduler

app = FastAPI(title="KrishiMitra API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router, tags=["WhatsApp"])


@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    start_scheduler()


@app.get("/health")
def health():
    return {"status": "ok", "service": "KrishiMitra", "version": "2.1.0"}
