# create_tables.py

# add this temporarily at top of create_tables.py
import os
from dotenv import load_dotenv
load_dotenv()
print("DB URL:", os.getenv("DATABASE_URL"))
from backend.services.db import engine, Base
from backend.models.price import MandiPrice  # importing the model registers it with Base

Base.metadata.create_all(bind=engine)
print("Tables created successfully on Supabase.")