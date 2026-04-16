from .auth import router as auth_router
from .library import router as library_router
from .profile import router as profile_router
from .reader import router as reader_router
from .visualize import router as visualize_router
from .voice import router as voice_router

__all__ = [
    "auth_router",
    "library_router",
    "profile_router",
    "reader_router",
    "visualize_router",
    "voice_router",
]
