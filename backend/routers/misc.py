"""Misc endpoints: root only.

Sprint 15B: `/upload-image` removed — zero callers; superseded by `/api/media/upload`.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    return {"message": "Hello World"}
