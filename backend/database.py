import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Supabase requires SSL — these args prevent connection errors
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
    # remove connect_args={"sslmode": "require"}
)

SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()

class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id           = Column(Integer, primary_key=True, index=True)
    farmer_id    = Column(String, nullable=True)
    disease_name = Column(String)
    confidence   = Column(Float)
    severity     = Column(String)
    crop_type    = Column(String, nullable=True)
    gps_lat      = Column(Float,  nullable=True)
    gps_lon      = Column(Float,  nullable=True)
    timestamp    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    Base.metadata.create_all(bind=engine)

def save_diagnosis(data: dict):
    db = SessionLocal()
    try:
        row = Diagnosis(**data)
        db.add(row)
        db.commit()
    finally:
        db.close()