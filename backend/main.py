from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from agent.whatsapp import router as agent_whatsapp_router
from routes.detect import router as detect_router
from routes.treatment import router as treatment_router
from routes.severity import router as severity_router
from routes.diagnose import router as diagnose_router
from routes.progression import router as progression_router
from routes.soil import router as soil_router
from routes.market import router as market_router
from routes.whatsapp import router as routes_whatsapp_router
from scheduler import scheduler, start_scheduler
from services.db import Base, engine
from services.price_fetcher import run_daily_fetch
from outbreak.routes import router as outbreak_router
from outbreak.scheduler import check_new_detections

Base.metadata.create_all(bind=engine)

app = FastAPI(title="KrishiMitra API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Working WhatsApp agent router
app.include_router(agent_whatsapp_router)

# Existing backend/routes routers
app.include_router(detect_router, prefix="/detect", tags=["Detection"])
app.include_router(treatment_router, prefix="/treatment", tags=["Treatment"])
app.include_router(severity_router, prefix="/severity", tags=["Severity"])
app.include_router(diagnose_router, prefix="/diagnose", tags=["Diagnose"])
app.include_router(progression_router, prefix="/progression", tags=["Progression"])
app.include_router(soil_router, prefix="/soil", tags=["Soil"])
app.include_router(market_router, prefix="/market", tags=["Market"])
app.include_router(routes_whatsapp_router)
app.include_router(agent_whatsapp_router)
app.include_router(outbreak_router, prefix="/outbreak")

from concurrent.futures import ThreadPoolExecutor
import asyncio

_executor = ThreadPoolExecutor(max_workers=1)

@app.on_event("startup")
async def startup() -> None:
    loop = asyncio.get_event_loop()
    
    def fetch_wrapper():
        run_daily_fetch()

    # Existing job
    scheduler.add_job(
        lambda: loop.run_in_executor(_executor, fetch_wrapper),
        trigger="cron",
        hour=0,
        minute=0,
        id="daily_price_fetch",
        replace_existing=True,
    )

    # ✅ NEW OUTBREAK MONITOR JOB (EVERY 5 SECONDS)
    scheduler.add_job(
        lambda: asyncio.run(check_new_detections()),
        trigger="interval",
        seconds=5,
        id="outbreak_monitor",
        replace_existing=True,
    )

    start_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown()


@app.get("/health")
def health():
    return {"status": "ok", "service": "KrishiMitra", "version": "2.0.0"}

