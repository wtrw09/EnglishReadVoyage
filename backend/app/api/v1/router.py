"""API v1路由。"""
from fastapi import APIRouter

from app.api.v1.endpoints import books, tts, auth, categories, dictionary, settings, vocabulary, audiobook, translation, pronunciation, admin_user_books


api_router = APIRouter()

# 包含端点路由
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(books.router, prefix="/books", tags=["books"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(tts.router, prefix="/tts", tags=["tts"])
api_router.include_router(dictionary.router, prefix="/dictionary", tags=["dictionary"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(vocabulary.router, prefix="/vocabulary", tags=["vocabulary"])
api_router.include_router(audiobook.router, prefix="/audiobook", tags=["audiobook"])
api_router.include_router(translation.router, prefix="/translation", tags=["translation"])
api_router.include_router(pronunciation.router, prefix="/pronunciation", tags=["pronunciation"])
api_router.include_router(admin_user_books.router, prefix="/admin", tags=["admin"])
