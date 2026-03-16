from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL     = os.getenv("REDIS_URL")
MODEL_PATH    = os.getenv("MODEL_PATH", "weights/best.pt")
UPLOAD_DIR    = "uploads"