# services/db.py
from database import engine, Base, SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()