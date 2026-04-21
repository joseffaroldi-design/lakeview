"""Misc endpoints: root + image upload."""
import base64
from fastapi import APIRouter, UploadFile, File, Header, Cookie

from auth import verify_session

router = APIRouter()


@router.get("/")
async def root():
    return {"message": "Hello World"}


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), authorization: str = Header(None), session_token: str = Cookie(None)):
    await verify_session(authorization, session_token)
    contents = await file.read()
    base64_image = base64.b64encode(contents).decode('utf-8')
    content_type = file.content_type or 'image/jpeg'
    data_url = f"data:{content_type};base64,{base64_image}"
    return {"image_url": data_url}
