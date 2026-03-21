# voice.py
import whisper
import httpx, tempfile, os

model = whisper.load_model("base")  # or "small" for better Hindi

async def transcribe_voice(media_url: str) -> str:
    """Download WhatsApp .ogg and transcribe with Whisper."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(media_url, 
                                auth=(os.getenv("TWILIO_ACCOUNT_SID"), 
                                      os.getenv("TWILIO_AUTH_TOKEN")))
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(resp.content)
        path = f.name
    
    result = model.transcribe(path, language="hi")  # auto-detects Hindi/English
    os.unlink(path)
    return result["text"]