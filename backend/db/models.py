from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func
from backend.db.database import Base


class Farmer(Base):
    __tablename__ = "farmers"

    phone_number = Column(String, primary_key=True, index=True)
    name = Column(String)
    location = Column(String)
    language = Column(String, default="Hindi")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FarmerCrop(Base):
    __tablename__ = "farmer_crops"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, ForeignKey("farmers.phone_number"))
    crop_name = Column(String)


class FarmerDisease(Base):
    __tablename__ = "farmer_diseases"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, ForeignKey("farmers.phone_number"))
    disease_name = Column(String)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
