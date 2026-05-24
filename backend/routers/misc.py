"""Misc endpoints: root + image upload."""
import base64
from fastapi import APIRouter, UploadFile, File, Header, Cookie, HTTPException

from auth import verify_session

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


@router.get("/")
async def root():
    return {"message": "Hello World"}


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}. Allowed: jpeg, png, webp, gif.")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Max size is {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    base64_image = base64.b64encode(contents).decode("utf-8")
    data_url = f"data:{content_type};base64,{base64_image}"
    return {"image_url": data_url}
