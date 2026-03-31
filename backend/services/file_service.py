import uuid, shutil, tempfile
from pathlib import Path
from fastapi import UploadFile

UPLOAD_DIR = Path(tempfile.gettempdir()) / "krishimitra"
UPLOAD_DIR.mkdir(exist_ok=True)

def save_upload(file: UploadFile) -> Path:
    ext  = Path(file.filename).suffix or ".jpg"
    path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return path

def cleanup(path: Path):
    if path and path.exists():
        path.unlink()
