from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import asyncio

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
import services.whatsapp_service as ws

Base.metadata.create_all(bind=engine)

_executor = ThreadPoolExecutor(max_workers=1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()

    scheduler.add_job(
        lambda: loop.run_in_executor(_executor, run_daily_fetch),
        trigger="cron", hour=0, minute=0,
        id="daily_price_fetch", replace_existing=True,
    )
    scheduler.add_job(
        check_new_detections,
        trigger="interval", seconds=100,
        id="outbreak_monitor", replace_existing=True,
    )

    start_scheduler()
    print("🚀 Scheduler started")
    yield

    if scheduler.running:
        scheduler.shutdown()
        print("🛑 Scheduler stopped")


app = FastAPI(title="KrishiMitra API", version="2.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


app.include_router(agent_whatsapp_router)
app.include_router(detect_router, prefix="/detect", tags=["Detection"])
app.include_router(treatment_router, prefix="/treatment", tags=["Treatment"])
app.include_router(severity_router, prefix="/severity", tags=["Severity"])
app.include_router(diagnose_router, prefix="/diagnose", tags=["Diagnose"])
app.include_router(progression_router, prefix="/progression", tags=["Progression"])
app.include_router(soil_router, prefix="/soil", tags=["Soil"])
app.include_router(market_router, prefix="/market", tags=["Market"])
app.include_router(routes_whatsapp_router)
app.include_router(outbreak_router, prefix="/outbreak")

@app.get("/health")
def health():
    return {"status": "ok", "service": "KrishiMitra", "version": "2.0.0"}