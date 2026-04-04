import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/krishimitra")

engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base         = declarative_base()


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id            = Column(Integer, primary_key=True, index=True)
    phone_number  = Column(String, nullable=False)
    commodity     = Column(String, nullable=False)
    market        = Column(String, nullable=True)
    target_price  = Column(Float, nullable=False)
    last_triggered_price = Column(Float, nullable=True)
    condition     = Column(String, default="above")   # "above" or "below"
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    triggered_at  = Column(DateTime, nullable=True)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()