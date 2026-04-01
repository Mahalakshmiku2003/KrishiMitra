from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from apscheduler.schedulers.background import BackgroundScheduler
from routers import diagnose
from routers.market import router as market_router
from services.price_fetcher import run_daily_fetch
#from database import init_db

from database import Base, engine
from models import price 

Base.metadata.create_all(bind=engine)

from config import UPLOAD_DIR
import os
abs_upload_dir = os.path.abspath(UPLOAD_DIR)
os.makedirs(abs_upload_dir, exist_ok=True)
print(f"DEBUG: Using upload directory at {abs_upload_dir}")

app = FastAPI(title="KrishiMitra API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
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
