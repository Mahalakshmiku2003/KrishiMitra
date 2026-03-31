import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.db import Base, engine

# Create all DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="KrishiMitra API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
<<<<<<< HEAD
    allow_headers=["*"]
)

#@app.on_event("startup")
#def startup():
 #   init_db()

app.include_router(diagnose.router)
app.include_router(market_router,prefix="/market",tags=["Market"])

scheduler = BackgroundScheduler()
scheduler.add_job(run_daily_fetch, "cron", hour=0, minute=0)
scheduler.start()

@app.get("/health")
def health():
    return {"status": "ok", "service": "KrishiMitra", "version": "2.0.0"}
=======
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
from routes.detect      import router as detect_router
from routes.treatment   import router as treatment_router
from routes.severity    import router as severity_router
from routes.diagnose    import router as diagnose_router
from routes.progression import router as progression_router
from routes.soil        import router as soil_router
from routes.market      import router as market_router
from routes.whatsapp    import router as whatsapp_router

app.include_router(detect_router,      prefix="/detect",      tags=["Detection"])
app.include_router(treatment_router,   prefix="/treatment",   tags=["Treatment"])
app.include_router(severity_router,    prefix="/severity",    tags=["Severity"])
app.include_router(diagnose_router,    prefix="/diagnose",    tags=["Diagnose"])
app.include_router(progression_router, prefix="/progression", tags=["Progression"])
app.include_router(soil_router,        prefix="/soil",        tags=["Soil"])
app.include_router(market_router,      prefix="/market",      tags=["Market"])
app.include_router(whatsapp_router)    # POST /webhook/whatsapp

# ── Scheduler — one instance only ─────────────────────────────────────────────
from scheduler import scheduler
from services.price_fetcher import run_daily_fetch

# Daily midnight price fetch
scheduler.add_job(
    run_daily_fetch,
    trigger="cron",
    hour=0,
    minute=0,
    id="daily_price_fetch",
    replace_existing=True,
)

@app.on_event("startup")
async def startup():
    scheduler.start()
    print("[Scheduler] Started — morning briefing 7am, price fetch midnight.")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    print("[Scheduler] Stopped.")

# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "KrishiMitra", "version": "2.0.0"}
>>>>>>> 98caa759f0b80b1598cb6a0f63dd3f81bd62a2c4
