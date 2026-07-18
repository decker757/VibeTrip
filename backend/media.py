"""Local media storage adapter for the MVP.

The API returns stable relative URLs, so this can later be replaced with an
S3/R2 adapter without changing the trip or Explore contracts.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile


MEDIA_ROOT = Path(os.getenv("VIBETRIP_MEDIA_DIR", Path(__file__).with_name("media")))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
MAX_MEDIA_BYTES = 20 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/webm", "video/quicktime"}


async def save_upload(trip_id: str, upload: UploadFile) -> dict:
    content_type = upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or ""
    if content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, WebP, GIF, MP4, WebM, or MOV file.")
    data = await upload.read(MAX_MEDIA_BYTES + 1)
    if len(data) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="Media files must be 20 MB or smaller.")
    extension = mimetypes.guess_extension(content_type) or Path(upload.filename or "memory").suffix or ".bin"
    filename = f"{uuid4().hex}{extension}"
    destination = MEDIA_ROOT / trip_id
    destination.mkdir(parents=True, exist_ok=True)
    (destination / filename).write_bytes(data)
    return {
        "id": uuid4().hex,
        "url": f"/media/{trip_id}/{filename}",
        "type": content_type,
        "name": upload.filename or filename,
        "size_bytes": len(data),
    }
