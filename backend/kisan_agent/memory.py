# memory.py
import psycopg2, json, os

conn = psycopg2.connect(os.getenv("DATABASE_URL"))

def get_farmer(phone: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM farmers WHERE phone = %s", (phone,))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO farmers (phone) VALUES (%s) RETURNING *", (phone,)
            )
            conn.commit()
            row = cur.fetchone()
    return {
        "phone": row[0], "name": row[1], "crops": row[2],
        "location": row[3], "history": row[4], "recent_messages": row[5]
    }

def save_message(phone: str, user_msg: str, bot_msg: str):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE farmers SET messages = (
                (COALESCE(messages, '[]'::jsonb) || %s::jsonb)
            )
            WHERE phone = %s
        """, (
            json.dumps([
                {"role": "human", "content": user_msg},
                {"role": "ai", "content": bot_msg}
            ]),
            phone
        ))
        conn.commit()