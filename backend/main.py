from fastapi import FastAPI
from routers import diagnose
#from database import init_db

app = FastAPI(title="CropDoc API")

#@app.on_event("startup")
#def startup():
 #   init_db()

app.include_router(diagnose.router)

@app.get("/health")
def health():
    return {"status": "KrishiMitra running"}