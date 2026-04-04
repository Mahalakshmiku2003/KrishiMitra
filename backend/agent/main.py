# backend/agent/main.py
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from agent.whatsapp import router as whatsapp_router
from agent.scheduler import start_scheduler, stop_scheduler

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

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
    start_scheduler()
    print("✅ KrishiMitra server started!")


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
