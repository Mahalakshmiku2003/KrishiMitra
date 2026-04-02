# backend/agent/main.py
import os
import socket
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from backend.agent.whatsapp import router as whatsapp_router
from backend.db.database import test_db_connection
from backend.scheduler import start_scheduler, stop_scheduler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)
print("📁 Loading .env from:", ENV_PATH)

try:
    socket.gethostbyname("google.com")
    print("🌐 Internet OK")
except Exception:
    print("❌ DNS/Internet issue detected")
    print("Try running: ipconfig /flushdns")

app = FastAPI(
    title="KrishiMitra API",
    description="AI crop doctor for Indian farmers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router)


@app.on_event("startup")
async def startup():
    """Called when server starts"""
    await test_db_connection()
    start_scheduler()
    print("KrishiMitra server started!")


@app.on_event("shutdown")
async def shutdown():
    """Called when server stops"""
    stop_scheduler()


@app.get("/")
def root():
    return {
        "app": "KrishiMitra",
        "tagline": "Har fasal ka dost",
        "status": "running ✅",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}

