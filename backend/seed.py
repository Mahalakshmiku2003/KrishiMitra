import sqlite3
import random
from datetime import datetime, timedelta, date

# Database connection
DB_PATH = 'krishimitra.db'

# Constants for seeding
COMMODITIES = ["Tomato", "Onion", "Potato"]
STATES = {
    "Maharashtra": ["Nashik", "Pune", "Mumbai"],
    "Karnataka": ["Bangalore", "Mysore", "Hubli"],
    "Uttar Pradesh": ["Lucknow", "Agra", "Kanpur"],
    "Gujarat": ["Ahmedabad", "Surat", "Rajkot"]
}

def seed_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing data to avoid duplicates/conflicts during testing
    cursor.execute("DELETE FROM diagnoses")
    cursor.execute("DELETE FROM mandi_prices")

    # 1. Seed Diagnoses
    diagnoses_sample = [
        (None, "Tomato Late Blight", 0.925, "Severe", "Tomato", 19.9975, 73.7898, datetime.now().isoformat()),
        (None, "Potato Early Blight", 0.882, "Moderate", "Potato", 19.0760, 72.8777, datetime.now().isoformat()),
        (None, "Corn Common Rust", 0.951, "Mild", "Corn", 28.6139, 77.2090, datetime.now().isoformat())
    ]
    cursor.executemany('''
        INSERT INTO diagnoses (farmer_id, disease_name, confidence, severity, crop_type, gps_lat, gps_lon, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', diagnoses_sample)

    # 2. Seed Robust Mandi Prices (Historical Trends)
    # We add 14 days of history for each market to make Forecast look good.
    base_date = date.today()
    
    mandi_records = []
    
    for state, markets in STATES.items():
        for market in markets:
            for commodity in COMMODITIES:
                # Random base price for this market/commodity
                base_price = random.randint(1000, 3000)
                
                # Create a 14-day trend
                for d in range(14):
                    current_date = base_date - timedelta(days=d)
                    
                    # Add some "trend" and "noise"
                    # We'll make it generally rising to look interesting
                    trend_factor = 1 + (0.01 * (14 - d)) 
                    noise = random.uniform(0.95, 1.05)
                    modal_price = round(base_price * trend_factor * noise)
                    min_p = round(modal_price * 0.9)
                    max_p = round(modal_price * 1.1)
                    
                    mandi_records.append((
                        state, 
                        market, # district as market for simplicity in seed
                        market, 
                        commodity, 
                        "Common", 
                        min_p, 
                        max_p, 
                        modal_price, 
                        current_date.isoformat(), 
                        datetime.now().isoformat()
                    ))

    cursor.executemany('''
        INSERT INTO mandi_prices (state, district, market, commodity, variety, min_price, max_price, modal_price, arrival_date, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', mandi_records)

    conn.commit()
    conn.close()
    print(f"Successfully seeded {len(mandi_records)} price records across {len(STATES)} states!")
    print("Historical data (14 days) added for Tomato, Onion, and Potato.")

if __name__ == "__main__":
    seed_data()
