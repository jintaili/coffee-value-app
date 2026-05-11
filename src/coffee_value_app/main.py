import logging
from pathlib import Path

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from coffee_value_app import __version__
from coffee_value_app.analysis import AnalysisService
from coffee_value_app.config import load_settings
from coffee_value_app.extractor import ExtractionError
from coffee_value_app.fetcher import BlockedUrlError, FetchError, InvalidUrlError
from coffee_value_app.history import DisabledHistoryStore, PostgresHistoryStore
from coffee_value_app.schemas import AnalyzeRequest, AnalyzeResponse, HistoryListResponse, HistoryResponseItem


STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Coffee Value App API",
        version=__version__,
    )
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    settings = load_settings()
    app.state.history_store = (
        PostgresHistoryStore(settings.database_url) if settings.database_url else DisabledHistoryStore()
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "coffee-value-app",
            "version": __version__,
        }

    @app.post("/api/analyze", response_model=AnalyzeResponse, tags=["analysis"])
    async def analyze(request_body: AnalyzeRequest, request: Request) -> AnalyzeResponse:
        service = getattr(request.app.state, "analysis_service", None)
        if service is None:
            service = AnalysisService()
        history_store = getattr(request.app.state, "history_store", DisabledHistoryStore())
        url = str(request_body.url)
        try:
            response = await service.analyze_url(url)
            await anyio.to_thread.run_sync(
                lambda: history_store.save_success(url=url, response=response.model_dump(mode="json"))
            )
            return response
        except InvalidUrlError as exc:
            logger.info("Analyze rejected invalid URL %s: %s", request_body.url, exc)
            await anyio.to_thread.run_sync(lambda: history_store.save_error(url=url, error=str(exc)))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except BlockedUrlError as exc:
            logger.info("Analyze blocked URL %s: %s", request_body.url, exc)
            await anyio.to_thread.run_sync(lambda: history_store.save_error(url=url, error=str(exc)))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FetchError as exc:
            logger.warning("Analyze fetch failed for %s: %s", request_body.url, exc, exc_info=True)
            await anyio.to_thread.run_sync(lambda: history_store.save_error(url=url, error=str(exc)))
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ExtractionError as exc:
            logger.warning("Analyze extraction failed for %s: %s", request_body.url, exc, exc_info=True)
            await anyio.to_thread.run_sync(lambda: history_store.save_error(url=url, error=str(exc)))
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/history", response_model=HistoryListResponse, tags=["analysis"])
    async def history(request: Request, limit: int = 25) -> HistoryListResponse:
        history_store = getattr(request.app.state, "history_store", DisabledHistoryStore())
        items = await anyio.to_thread.run_sync(lambda: history_store.list_recent(limit=limit))
        return HistoryListResponse(
            items=[
                HistoryResponseItem(
                    id=item.id,
                    created_at=item.created_at,
                    url=item.url,
                    status=item.status,
                    response=item.response,
                    error=item.error,
                )
                for item in items
            ]
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
