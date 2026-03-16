#Compresses images to ≤400 KB for 2G-friendly uploads.

from PIL import Image
import io

def compress_image(file_bytes: bytes, max_kb: int = 400) -> bytes:
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img.thumbnail((1280, 1280), Image.LANCZOS)

    output = io.BytesIO()
    quality = 85

    while quality > 20:
        output.seek(0)
        output.truncate()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        if output.tell() <= max_kb * 1024:
            break
        quality -= 10

    output.seek(0)
    return output.read()