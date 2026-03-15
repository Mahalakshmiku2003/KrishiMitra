from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routes.detect import router as detect_router
from routes.treatment import router as treatment_router
from routes.severity import router as severity_router
from routes.diagnose import router as diagnose_router
from routes.progression import router as progression_router
from routes.soil import router as soil_router

app = FastAPI(title="KrishiMitra API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(detect_router,      prefix="/detect",      tags=["Detection"])
app.include_router(treatment_router,   prefix="/treatment",   tags=["Treatment"])
app.include_router(severity_router,    prefix="/severity",    tags=["Severity"])
app.include_router(diagnose_router,    prefix="/diagnose",    tags=["Diagnose"])
app.include_router(progression_router, prefix="/progression", tags=["Progression"])
app.include_router(soil_router,        prefix="/soil",        tags=["Soil"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "KrishiMitra", "version": "2.0.0"}