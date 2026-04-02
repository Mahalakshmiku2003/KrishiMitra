import os
import socket
import asyncio

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
print("📁 Loading .env from:", ENV_PATH)
load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL not found. Check .env location")

print("🔍 DATABASE_URL:", DATABASE_URL[:50] + "...")

if "supabase.co" not in DATABASE_URL:
    print("⚠️ WARNING: Not a Supabase URL")

DATABASE_URL = DATABASE_URL.strip().strip('"').strip("'")
if not DATABASE_URL.startswith("postgresql://"):
    raise ValueError("Invalid DATABASE_URL format")

db_host = DATABASE_URL.split("@", 1)[1].split(":", 1)[0]
print("DB HOST:", db_host)
try:
    socket.gethostbyname(db_host)
    print(f"🌐 DB HOST OK: {db_host}")
except Exception as e:
    print(f"❌ DB HOST ERROR:", e)

DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

url = make_url(DATABASE_URL)
if "pgbouncer" in url.query:
    query = dict(url.query)
    query.pop("pgbouncer", None)
    url = url.set(query=query)

DATABASE_URL = url.render_as_string(hide_password=False)

engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"ssl": "require"},
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


async def test_db():
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            print("✅ DB CONNECTED SUCCESSFULLY (ASYNC)")
            return True
    except Exception as e:
        print("❌ DB CONNECTION FAILED:", e)
        return False


async def test_db_connection():
    return await test_db()


try:
    asyncio.get_running_loop().create_task(test_db())
except RuntimeError:
    pass
