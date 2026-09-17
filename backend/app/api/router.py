from fastapi import APIRouter

from app.api.routes import admins, auth, games, health, notices, players, public, scoring, seasons, settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admins.router)
api_router.include_router(seasons.router)
api_router.include_router(seasons.admin_router)
api_router.include_router(scoring.router)
api_router.include_router(settings.router)
api_router.include_router(settings.admin_router)
api_router.include_router(public.router)
api_router.include_router(games.router)
api_router.include_router(players.router)
api_router.include_router(notices.router)
api_router.include_router(notices.admin_router)
