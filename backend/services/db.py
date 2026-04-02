import os
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = (
    os.getenv("SUPABASE_DB_URL")
    or os.getenv("SUPABASE_DATABASE_URL")
    or os.getenv("DATABASE_URL")
)


if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing in .env")

engine_kwargs = {}
try:
    parsed = urlparse(DATABASE_URL)
    # Supabase Postgres requires SSL.
    if "supabase.co" in parsed.hostname if parsed.hostname else False:
        engine_kwargs["connect_args"] = {"sslmode": "require"}
except Exception:
    pass

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
