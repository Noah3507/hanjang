from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import asyncio

from app.api.health import router as health_router
from app.api.photos import router as photo_router
from app.services.photo_execution import PhotoExecution
from app.config import Settings
from app.api.uploads import router as upload_router
from app.api.errors import upload_error, validation_error
from app.api.upload_limits import UploadLimitMiddleware
from app.services.uploads import PrivateUploadStore, UploadError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    storage = PrivateUploadStore(settings.upload_root)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        await asyncio.to_thread(storage.cleanup)
        async def sweep():
            while True:
                await asyncio.sleep(60)
                await asyncio.to_thread(storage.cleanup)
        task = asyncio.create_task(sweep())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    application = FastAPI(title="Hanjang API", version="0.1.0", lifespan=lifespan)
    application.state.upload_store = storage
    application.state.photo_processor = PhotoExecution(settings.photo_model_path, settings.photo_timeout_seconds, settings.photo_max_side)
    application.add_exception_handler(UploadError, upload_error)
    application.add_exception_handler(RequestValidationError, validation_error)
    application.add_middleware(UploadLimitMiddleware, storage=storage)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Accept", "Content-Type", "X-Hanjang-Session"],
    )
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(upload_router, prefix="/api/v1")
    application.include_router(photo_router, prefix="/api/v1")
    # Requested local health path; same response as the versioned contract.
    application.include_router(health_router, include_in_schema=False)
    return application


app = create_app()
