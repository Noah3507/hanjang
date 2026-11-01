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
from app.api.analysis import router as analysis_router
from app.services.analysis_execution import AnalysisExecution
from app.services.analysis_store import AnalysisStore
from app.api.copy import router as copy_router
from app.services.copy_store import CopyStore
from app.services.copy_provider import build_copy_provider
from app.api.rendering import router as render_router
from app.services.render_store import RenderStore
from app.services.render_execution import RenderExecution
from app.api.ranking import router as ranking_router
from app.services.ranking_store import RankingStore
from app.api.editing import router as editor_router
from app.services.editor_store import EditorStore
from app.services.export_service import ExportService
from app.api.diagnostics import router as diagnostics_router
from app.services.diagnostics_store import DiagnosticsStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    storage = PrivateUploadStore(settings.upload_root)
    analysis_executor = AnalysisExecution(settings.analysis_python, settings.analysis_model_path,
        settings.analysis_timeout_seconds, settings.analysis_idle_seconds)
    copy_provider = build_copy_provider(settings)

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
            await asyncio.to_thread(copy_provider.close)
            await asyncio.to_thread(analysis_executor.close)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    application = FastAPI(title="Hanjang API", version="0.1.0", lifespan=lifespan)
    application.state.upload_store = storage
    application.state.analysis_executor = analysis_executor
    application.state.analysis_store = AnalysisStore(storage, analysis_executor)
    application.state.copy_store = CopyStore(storage, application.state.analysis_store, copy_provider, settings.copy_max_retries)
    application.state.render_store = RenderStore(storage, application.state.copy_store, RenderExecution())
    application.state.ranking_store = RankingStore(storage, application.state.render_store)
    application.state.editor_store = EditorStore(application.state.render_store)
    application.state.export_service = ExportService(application.state.render_store)
    application.state.diagnostics_store = DiagnosticsStore(application.state.render_store)
    application.state.photo_processor = PhotoExecution(settings.photo_model_path, settings.photo_timeout_seconds, settings.photo_max_side)
    application.add_exception_handler(UploadError, upload_error)
    application.add_exception_handler(RequestValidationError, validation_error)
    application.add_middleware(UploadLimitMiddleware, storage=storage)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Accept", "Content-Type", "X-Hanjang-Session"],
    )
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(upload_router, prefix="/api/v1")
    application.include_router(photo_router, prefix="/api/v1")
    application.include_router(analysis_router, prefix="/api/v1")
    application.include_router(copy_router, prefix="/api/v1")
    application.include_router(render_router, prefix="/api/v1")
    application.include_router(ranking_router, prefix="/api/v1")
    application.include_router(editor_router, prefix="/api/v1")
    application.include_router(diagnostics_router, prefix="/api/v1")
    # Requested local health path; same response as the versioned contract.
    application.include_router(health_router, include_in_schema=False)
    return application


app = create_app()
