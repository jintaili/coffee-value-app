from __future__ import annotations

from pathlib import Path

from coffee_value_app.config import Settings, load_settings
from coffee_value_app.extractor import OpenAILLMExtractor
from coffee_value_app.fetcher import fetch_product_page
from coffee_value_app.html_text import html_to_text
from coffee_value_app.model_runtime import ModelService
from coffee_value_app.product_data import embedded_product_data_to_text
from coffee_value_app.roaster_country import infer_roaster_country_from_url
from coffee_value_app.roaster_resolver import (
    OpenAIWebRoasterResolver,
    RoasterResolutionError,
    apply_roaster_country_resolution,
)
from coffee_value_app.schemas import (
    UNKNOWN,
    AnalyzeRequest,
    AnalyzeResponse,
    PageExtraction,
    SourceSnippet,
    to_model_input,
)


class AnalysisService:
    def __init__(
        self,
        *,
        extractor: OpenAILLMExtractor | None = None,
        roaster_resolver: OpenAIWebRoasterResolver | None = None,
        model_service: ModelService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.extractor = extractor or OpenAILLMExtractor(settings=self.settings)
        self.roaster_resolver = roaster_resolver or OpenAIWebRoasterResolver(settings=self.settings)
        self.model_service = model_service or ModelService()

    async def analyze_url(self, url: str, *, resolve_roaster_country: bool = True) -> AnalyzeResponse:
        page = await fetch_product_page(url)
        page_text = build_page_context(page.text, page.final_url)
        extraction = await self.extractor.extract(url=page.final_url, page_text=page_text)
        extraction = apply_domain_roaster_country(extraction, page.final_url)
        if resolve_roaster_country and extraction.coffee.roaster_country == UNKNOWN:
            try:
                resolution = await self.roaster_resolver.resolve(
                    roaster=extraction.coffee.roaster,
                    url=page.final_url,
                )
            except RoasterResolutionError:
                resolution = None
            if resolution is not None:
                extraction = extraction.model_copy(
                    update={"coffee": apply_roaster_country_resolution(extraction.coffee, resolution)}
                )

        model_input = to_model_input(extraction.coffee, extraction.price)
        return AnalyzeResponse(
            input=AnalyzeRequest(url=page.final_url),
            coffee=extraction.coffee,
            price=extraction.price,
            model_input=model_input,
            prediction=self.model_service.predict(model_input, extraction.price),
            quality=extraction.quality,
        )


class FixtureAnalysisService:
    def __init__(self, fixture_path: Path, model_service: ModelService | None = None) -> None:
        self.fixture_path = fixture_path
        self.model_service = model_service or ModelService()

    async def analyze_url(self, url: str, *, resolve_roaster_country: bool = True) -> AnalyzeResponse:
        extraction = PageExtraction.model_validate_json(self.fixture_path.read_text(encoding="utf-8"))
        model_input = to_model_input(extraction.coffee, extraction.price)
        return AnalyzeResponse(
            input=AnalyzeRequest(url=url),
            coffee=extraction.coffee,
            price=extraction.price,
            model_input=model_input,
            prediction=self.model_service.predict(model_input, extraction.price),
            quality=extraction.quality,
        )


def build_page_context(html: str, url: str) -> str:
    blocks = [
        html_to_text(html),
        embedded_product_data_to_text(html, url),
        roaster_country_context(url),
    ]
    return "\n\n".join(block for block in blocks if block)


def roaster_country_context(url: str) -> str:
    inferred = infer_roaster_country_from_url(url)
    if not inferred:
        return ""
    country, reason = inferred
    return (
        "URL/domain-derived roaster evidence:\n"
        f"- inferred_roaster_country={country}; evidence={reason}\n"
        "Use this for roaster_country when page text does not state a more specific roaster country."
    )


def apply_domain_roaster_country(extraction: PageExtraction, url: str) -> PageExtraction:
    if extraction.coffee.roaster_country != UNKNOWN:
        return extraction
    inferred = infer_roaster_country_from_url(url)
    if not inferred:
        return extraction
    country, reason = inferred
    snippets = [
        *extraction.coffee.source_snippets,
        SourceSnippet(field="roaster_country", snippet=reason),
    ]
    return extraction.model_copy(
        update={
            "coffee": extraction.coffee.model_copy(
                update={
                    "roaster_country": country,
                    "source_snippets": snippets,
                }
            )
        }
    )
