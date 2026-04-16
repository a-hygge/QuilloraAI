import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import rag
from app.config import settings
from app.routers import (
    auth_router,
    library_router,
    profile_router,
    reader_router,
    visualize_router,
    voice_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
for noisy in ("httpcore", "httpx", "urllib3", "websockets"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        rag.refresh_index()
        print(f"[LibMate] Index built for {len(rag._index())} book(s).")
    except Exception as e:
        print(f"[LibMate] Warning: could not build index yet ({e}). Run scripts/ingest.py.")
    print(f"[LibMate] {settings.APP_NAME} v{settings.APP_VERSION} ready at http://{settings.HOST}:{settings.PORT}")
    yield
    print("[LibMate] Shutting down.")


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(library_router)
app.include_router(reader_router)
app.include_router(visualize_router)
app.include_router(voice_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "name": settings.APP_NAME, "version": settings.APP_VERSION}


app.mount(
    "/static",
    StaticFiles(directory=str(settings.WEB_DIR / "static")),
    name="static",
)


@app.get("/")
@app.get("/library")
@app.get("/wall")
@app.get("/about")
@app.get("/login")
@app.get("/register")
@app.get("/me")
async def index():
    return FileResponse(str(settings.WEB_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
