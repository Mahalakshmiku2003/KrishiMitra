
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, UniqueConstraint
from datetime import datetime
from database import Base 

class MandiPrice(Base):
    __tablename__ = "mandi_prices"

    id           = Column(Integer, primary_key=True, index=True)
    state        = Column(String, nullable=False, index=True)
    district     = Column(String, nullable=False)
    market       = Column(String, nullable=False, index=True)
    commodity    = Column(String, nullable=False, index=True)
    variety      = Column(String)
    min_price    = Column(Float)
    max_price    = Column(Float)
    modal_price  = Column(Float)
    arrival_date = Column(Date, nullable=False)
    fetched_at   = Column(DateTime, default=datetime.utcnow)

    # Prevent duplicate records for same market+commodity+date
    __table_args__ = (
        UniqueConstraint("market", "commodity", "variety", "arrival_date",
                         name="uq_market_commodity_date"),
    )
