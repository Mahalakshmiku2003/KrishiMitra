from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.sql import func
from sqlalchemy.orm import validates
from backend.db.database import Base


def safe_dict(value):
    if isinstance(value, dict):
        return value
    return {}


class Farmer(Base):
    __tablename__ = "farmers"

    phone = Column(String, primary_key=True, index=True)
    name = Column(String)
    crops = Column(
        MutableList.as_mutable(ARRAY(String)),
        nullable=False,
        default=list,
        server_default=text("'{}'"),
    )
    location = Column(String)
    history = Column(
        MutableList.as_mutable(JSONB),
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    messages = Column(
        MutableList.as_mutable(JSONB),
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    soil_type = Column(String)
    last_seen = Column(DateTime(timezone=True))
    last_detection = Column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    @validates("last_detection")
    def validate_last_detection(self, key, value):
        if not isinstance(value, dict):
            print("❌ AUTO-FIX last_detection:", value)
            return {}
        return value

    @property
    def phone_number(self):
        return self.phone

    @phone_number.setter
    def phone_number(self, value):
        self.phone = value

    @property
    def language(self):
        return "hindi"

    @language.setter
    def language(self, value):
        return None


class MandiPrice(Base):
    __tablename__ = "mandi_prices"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=False)
    market = Column(String, nullable=False, index=True)
    commodity = Column(String, nullable=False, index=True)
    variety = Column(String)
    min_price = Column(Float)
    max_price = Column(Float)
    modal_price = Column(Float)
    arrival_date = Column(Date, nullable=False, index=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "market",
            "commodity",
            "variety",
            "arrival_date",
            name="uq_market_commodity_date",
        ),
        Index("ix_mandi_prices_commodity_district", "commodity", "district"),
    )
