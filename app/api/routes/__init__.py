"""API Routes package."""

from fastapi import APIRouter

from app.api.routes.books import router as books_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.previews import router as previews_router
from app.api.routes.reviews import router as reviews_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(books_router)
api_router.include_router(documents_router)
api_router.include_router(previews_router)
api_router.include_router(reviews_router)

__all__ = ["api_router"]

