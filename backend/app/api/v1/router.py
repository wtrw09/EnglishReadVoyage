"""API v1路由。"""
from fastapi import APIRouter

from app.api.v1.endpoints import books, tts, auth


api_router = APIRouter()

# 包含端点路由
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(books.router, prefix="/books", tags=["books"])
api_router.include_router(tts.router, prefix="/tts", tags=["tts"])
