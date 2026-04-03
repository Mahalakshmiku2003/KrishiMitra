from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.routes.whatsapp import router as whatsapp_router
from backend.services.db import Base, engine
from backend.scheduler import start_scheduler

Base.metadata.create_all(bind=engine)

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
    start_scheduler()


@app.get("/health")
def health():
    return {"status": "ok", "service": "KrishiMitra", "version": "2.1.0"}
