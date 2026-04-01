import os
import tempfile
import httpx
import whisper


model = whisper.load_model("base")


async def transcribe_voice(media_url: str) -> str:
    """Download WhatsApp voice media and transcribe it."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            media_url,
            auth=(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")),
        )
        resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(resp.content)
        path = f.name

    try:
        result = model.transcribe(path, language="hi")
        return result.get("text", "").strip()
    finally:
        if os.path.exists(path):
            os.unlink(path)
