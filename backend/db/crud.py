from sqlalchemy.future import select
from db.models import Farmer, FarmerCrop, FarmerDisease


# ─── Create or Update Farmer ─────────────────────────────
from sqlalchemy.future import select
from db.models import Farmer


async def upsert_farmer(db, phone, location=None, language=None):
    result = await db.execute(select(Farmer).where(Farmer.phone_number == phone))
    farmer = result.scalar_one_or_none()

    location = normalize(location)
    language = normalize(language)

    if not farmer:
        farmer = Farmer(
            phone_number=phone, location=location, language=language or "hindi"
        )
        db.add(farmer)
    else:
        # ✅ Update ONLY if new value exists
        if location:
            farmer.location = location
        if language:
            farmer.language = language

    await db.commit()
    return farmer


# ─── Add Crop ────────────────────────────────────────────
from db.models import FarmerCrop


async def add_crop(db, phone, crop):
    crop = normalize(crop)

    if not crop:
        return

    # Check if already exists
    result = await db.execute(
        select(FarmerCrop).where(
            FarmerCrop.farmer_id == phone, FarmerCrop.crop_name == crop
        )
    )

    exists = result.scalar_one_or_none()

    if exists:
        print(f"⚠️ Crop already exists: {crop}")
        return

    db.add(FarmerCrop(farmer_id=phone, crop_name=crop))
    await db.commit()


def normalize(text: str):
    if not text:
        return None
    return text.strip().lower()


# ─── Add Disease ─────────────────────────────────────────
from db.models import FarmerDisease


async def add_disease(db, phone, disease):
    disease = normalize(disease)

    if not disease:
        return

    # 🔥 Delete old diseases
    await db.execute(
        FarmerDisease.__table__.delete().where(FarmerDisease.farmer_id == phone)
    )

    # Insert latest
    db.add(FarmerDisease(farmer_id=phone, disease_name=disease))

    await db.commit()


# ─── Get Full Profile ────────────────────────────────────
async def get_farmer_profile(db, phone):
    farmer = await db.get(Farmer, phone)

    crops = await db.execute(
        select(FarmerCrop.crop_name).where(FarmerCrop.farmer_id == phone)
    )

    diseases = await db.execute(
        select(FarmerDisease.disease_name)
        .where(FarmerDisease.farmer_id == phone)
        .order_by(FarmerDisease.detected_at.desc())
    )

    return {
        "farmer": farmer,
        "crops": [c[0] for c in crops.all()],
        "recent_disease": diseases.scalars().first(),
    }
