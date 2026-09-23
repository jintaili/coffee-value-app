from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from coffee_value_app.config import Settings, load_settings
from coffee_value_app.currency import CurrencyConverter
from coffee_value_app.fetcher import fetch_product_page
from coffee_value_app.html_text import html_to_text
from coffee_value_app.jev_extractor import JevExtractor
from coffee_value.extraction.questions import MODEL as JEV_MODEL
from coffee_value_app.model_runtime import ModelService
from coffee_value_app.product_data import embedded_product_data_to_text
from coffee_value_app.roaster_country import infer_roaster_country_from_url
from coffee_value_app.schemas import (
    UNKNOWN,
    AnalyzeRequest,
    AnalyzeResponse,
    PageExtraction,
    PredictionResult,
    PricePrediction,
    RatingPrediction,
    SourceSnippet,
    ValuePrediction,
    to_model_input,
)


class AnalysisService:
    def __init__(
        self,
        *,
        extractor: JevExtractor | None = None,
        currency_converter: CurrencyConverter | None = None,
        model_service: ModelService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.extractor = extractor or JevExtractor()
        self.currency_converter = currency_converter or CurrencyConverter()
        self.model_service = model_service or default_model_service()

    async def analyze_url(self, url: str, *, resolve_roaster_country: bool = True) -> AnalyzeResponse:
        page = await fetch_product_page(url)
        page_text = build_page_context(page.text, page.final_url)
        jev_result = await self.extractor.extract(url=page.final_url, page_text=page_text, html=page.text)
        extraction = jev_result.page
        extraction = apply_domain_roaster_country(extraction, page.final_url)
        extraction = extraction.model_copy(update={"price": await self.currency_converter.normalize_to_usd(extraction.price)})
        model_input = to_model_input(extraction.coffee, extraction.price)
        prediction = (self.model_service.predict(model_input, extraction.price, jev_record=jev_result.record)
                      if extraction.page_type == "coffee_product" else PredictionResult(
                          rating=RatingPrediction(model_version="not-run"),
                          price=PricePrediction(model_version="not-run"),
                          value=ValuePrediction(verdict="not_appraised")))
        return AnalyzeResponse(
            input=AnalyzeRequest(url=page.final_url),
            page_type=extraction.page_type,
            is_specialty_coffee=extraction.is_specialty_coffee,
            coffee=extraction.coffee,
            price=extraction.price,
            model_input=model_input,
            prediction=prediction,
            extraction_model=JEV_MODEL,
            quality=extraction.quality,
        )


class FixtureAnalysisService:
    def __init__(self, fixture_path: Path, model_service: ModelService | None = None) -> None:
        self.fixture_path = fixture_path
        self.model_service = model_service or default_model_service()

    async def analyze_url(self, url: str, *, resolve_roaster_country: bool = True) -> AnalyzeResponse:
        extraction = PageExtraction.model_validate_json(self.fixture_path.read_text(encoding="utf-8"))
        model_input = to_model_input(extraction.coffee, extraction.price)
        return AnalyzeResponse(
            input=AnalyzeRequest(url=url),
            page_type=extraction.page_type,
            is_specialty_coffee=extraction.is_specialty_coffee,
            coffee=extraction.coffee,
            price=extraction.price,
            model_input=model_input,
            prediction=self.model_service.predict(model_input, extraction.price),
            extraction_model="fixture",
            quality=extraction.quality,
        )


def build_page_context(html: str, url: str) -> str:
    blocks = [
        html_to_text(html),
        embedded_product_data_to_text(html, url),
        roaster_country_context(url),
    ]
    return "\n\n".join(block for block in blocks if block)


@lru_cache(maxsize=1)
def default_model_service() -> ModelService:
    return ModelService()


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
