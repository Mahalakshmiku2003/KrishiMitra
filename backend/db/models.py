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


class Farmer(Base):
    __tablename__ = "farmers"

    phone = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)

    crops = Column(
        MutableList.as_mutable(ARRAY(String)),
        nullable=False,
        default=list,
        server_default=text("'{}'"),
    )

    location = Column(String, nullable=True)

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
    soil_type = Column(String, nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)

    last_detection = Column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    language = Column(String, nullable=True, default=None)

    @validates("last_detection")
    def validate_last_detection(self, key, value):
        return value if isinstance(value, dict) else {}

    @property
    def phone_number(self):
        return self.phone

    @phone_number.setter
    def phone_number(self, value):
        self.phone = value


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


class InboundMessage(Base):
    __tablename__ = "inbound_messages"

    provider_message_id = Column(String, primary_key=True)
    phone = Column(String, nullable=False, index=True)
    body = Column(String, nullable=True)
    status = Column(String, nullable=False, default="processing")
    response_xml = Column(String, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_inbound_messages_phone_created", "phone", "created_at"),
    )
