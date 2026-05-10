from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from coffee_value_app import __version__
from coffee_value_app.analysis import AnalysisService
from coffee_value_app.extractor import ExtractionError
from coffee_value_app.fetcher import BlockedUrlError, FetchError, InvalidUrlError
from coffee_value_app.schemas import AnalyzeRequest, AnalyzeResponse


STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Coffee Value App API",
        version=__version__,
    )
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
        try:
            return await service.analyze_url(str(request_body.url))
        except InvalidUrlError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except BlockedUrlError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ExtractionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
