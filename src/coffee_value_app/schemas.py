from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


UNKNOWN = "unknown"


class ProcessMethod(StrEnum):
    WASHED = "washed"
    NATURAL = "natural"
    HONEY = "honey"
    ANAEROBIC = "anaerobic"
    CARBONIC_MACERATION = "carbonic_maceration"
    WET_HULLED = "wet_hulled"
    LACTIC = "lactic"
    UNKNOWN = UNKNOWN


class Variety(StrEnum):
    GESHA = "gesha"
    BOURBON = "bourbon"
    TYPICA = "typica"
    CATURRA = "caturra"
    CATUAI = "catuai"
    SL28 = "sl28"
    SL34 = "sl34"
    PACAMARA = "pacamara"
    MARAGOGIPE = "maragogipe"
    MOKKA = "mokka"
    MOKKITA = "mokkita"
    PINK_BOURBON = "pink_bourbon"
    RUIRU = "ruiru"
    CASTILLO = "castillo"
    JAVA = "java"
    UNKNOWN = UNKNOWN


class AnalyzeRequest(BaseModel):
    url: AnyHttpUrl


class SourceSnippet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    snippet: str


class ExtractedCoffee(BaseModel):
    """Human-facing extraction result from a product page.

    variety and process_method hold verbatim page terms (exact names as stated,
    e.g. "SL-9", "white honey"). Normalization into the ML model vocabulary happens
    deterministically in to_model_input, never in the LLM extraction.
    """

    model_config = ConfigDict(extra="forbid")

    coffee_name: str | None
    roaster: str | None
    roaster_location: str | None
    roaster_country: str
    origin_country: str
    origin_region: str
    process_method: list[str]
    variety: list[str]
    producer_or_farm: str | None
    altitude: str | None
    roast_level: str | None = None
    harvest_period: str | None = None
    is_blend: bool
    is_espresso: bool
    is_decaf: bool
    is_coferment_or_infused: bool = False
    sensory_text: str
    display_tasting_notes: str = ""
    producer_text: str
    source_snippets: list[SourceSnippet]

    @field_validator("origin_country", "origin_region", "roaster_country", mode="before")
    @classmethod
    def default_blank_labels(cls, value: str | None) -> str:
        if value is None or not str(value).strip():
            return UNKNOWN
        return str(value).strip()

    @field_validator("process_method", mode="before")
    @classmethod
    def default_process(cls, value: list[str] | str | None) -> list[str]:
        return normalize_list_value(value)

    @field_validator("variety", mode="before")
    @classmethod
    def default_variety(cls, value: list[str] | str | None) -> list[str]:
        return normalize_list_value(value)

    @model_validator(mode="after")
    def drop_unknown_when_specific_values_exist(self) -> "ExtractedCoffee":
        if len(self.process_method) > 1 and any(v.lower() == UNKNOWN for v in self.process_method):
            self.process_method = [v for v in self.process_method if v.lower() != UNKNOWN]
        if len(self.variety) > 1 and any(v.lower() == UNKNOWN for v in self.variety):
            self.variety = [v for v in self.variety if v.lower() != UNKNOWN]
        return self


class ExtractedPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listed_price: float | None = Field(ge=0)
    listed_currency: str | None
    original_listed_price: float | None = Field(default=None, ge=0)
    original_listed_currency: str | None = None
    bag_size_value: float | None = Field(gt=0)
    bag_size_unit: Literal["g", "kg", "oz", "lb"] | None
    package_grams: float | None = Field(gt=0)
    bags_count: int | None = Field(default=None, ge=1)
    price_100g_usd: float | None = Field(gt=0)
    price_type: Literal["one_time", "subscription", "membership", "unknown"] = "unknown"
    availability: Literal["in_stock", "sold_out", "preorder", "unknown"] = "unknown"
    assumptions: list[str]


class ModelInput(BaseModel):
    """Fields consumed by both predictors, plus package grams for price."""

    model_config = ConfigDict(extra="forbid")

    origin_country: str = UNKNOWN
    process_method: str = UNKNOWN
    variety: str = UNKNOWN
    is_blend: str
    is_espresso: str
    is_decaf: str
    producer_or_farm_present: str
    altitude_present: str
    roaster_country: str = UNKNOWN
    sensory_text: str = ""
    producer_text: str = ""
    package_grams: float | None = Field(default=None, gt=0)


class RatingPrediction(BaseModel):
    predicted: float | None = None
    interval_low: float | None = None
    interval_high: float | None = None
    model_version: str


class PricePrediction(BaseModel):
    predicted_price_100g_usd: float | None = None
    predicted_bag_price_usd: float | None = None
    interval_low: float | None = None
    interval_high: float | None = None
    model_version: str


class ValuePrediction(BaseModel):
    verdict: str
    listed_vs_predicted_delta_pct: float | None = None


class PredictionResult(BaseModel):
    rating: RatingPrediction
    price: PricePrediction
    value: ValuePrediction


class QualityReport(BaseModel):
    extraction_quality: Literal["good", "partial", "poor"]
    missing_fields: list[str]
    warnings: list[str]


PageType = Literal["coffee_product", "coffee_equipment", "other_product", "not_a_product_page"]


class PageExtraction(BaseModel):
    """Structured output expected from the LLM extractor."""

    model_config = ConfigDict(extra="forbid")

    page_type: PageType = "coffee_product"
    is_specialty_coffee: bool | None = None
    coffee: ExtractedCoffee
    price: ExtractedPrice
    quality: QualityReport


class AnalyzeResponse(BaseModel):
    api_version: Literal["v1"] = "v1"
    status: Literal["ok"] = "ok"
    input: AnalyzeRequest
    page_type: PageType = "coffee_product"
    is_specialty_coffee: bool | None = None
    coffee: ExtractedCoffee
    price: ExtractedPrice
    model_input: ModelInput
    prediction: PredictionResult
    quality: QualityReport


class HistoryResponseItem(BaseModel):
    id: UUID
    created_at: datetime
    url: str
    status: Literal["ok", "error"]
    response: AnalyzeResponse | None = None
    error: str | None = None


class HistoryListResponse(BaseModel):
    items: list[HistoryResponseItem]


def normalize_list_value(value: list[str] | str | None) -> list[str]:
    if value is None:
        return [UNKNOWN]
    if isinstance(value, str):
        value = value.split("|")
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned or [UNKNOWN]


def joined_model_labels(values: list[StrEnum]) -> str:
    labels = sorted({str(value) for value in values if str(value) != UNKNOWN})
    return "|".join(labels) if labels else UNKNOWN


# Verbatim-term to model-vocabulary mapping. Patterns are ported from the training
# feature contract (coffee-value-autoresearch coffee_value/features.py) so that
# inference-time normalization matches how training labels were derived.
_PROCESS_VOCAB_PATTERNS: list[tuple[ProcessMethod, re.Pattern[str]]] = [
    (ProcessMethod.CARBONIC_MACERATION, re.compile(r"\bcarbonic\s+maceration\b", re.I)),
    (ProcessMethod.WET_HULLED, re.compile(r"\bwet[-\s]?hulled\b|\bgiling\s+basah\b", re.I)),
    (ProcessMethod.ANAEROBIC, re.compile(r"\banaerobic\b", re.I)),
    (ProcessMethod.LACTIC, re.compile(r"\blactic\b", re.I)),
    (
        ProcessMethod.HONEY,
        re.compile(
            r"\bhoney[-\s]?(?:processed|process)?\b|\bblack honey\b|\bred honey\b"
            r"|\byellow honey\b|\bwhite honey\b",
            re.I,
        ),
    ),
    (
        ProcessMethod.NATURAL,
        re.compile(r"\bnatural[-\s]?(?:processed|process)?\b|\bdry[-\s]processed\b|\bdried in the fruit\b", re.I),
    ),
    (
        ProcessMethod.WASHED,
        re.compile(r"\bwashed\b|\bwet[-\s]processed\b|\bfully washed\b|\btraditional washed\b", re.I),
    ),
]

_VARIETY_VOCAB_PATTERNS: list[tuple[Variety, re.Pattern[str]]] = [
    (Variety.PINK_BOURBON, re.compile(r"\bpink\s+bourbon\b", re.I)),
    (Variety.GESHA, re.compile(r"\bgesha\b|\bgeisha\b", re.I)),
    (Variety.BOURBON, re.compile(r"\bbourbon\b", re.I)),
    (Variety.TYPICA, re.compile(r"\btypica\b", re.I)),
    (Variety.CATURRA, re.compile(r"\bcaturra\b", re.I)),
    (Variety.CATUAI, re.compile(r"\bcatuai\b", re.I)),
    (Variety.SL28, re.compile(r"\bsl\s*[-]?\s*28\b", re.I)),
    (Variety.SL34, re.compile(r"\bsl\s*[-]?\s*34\b", re.I)),
    (Variety.PACAMARA, re.compile(r"\bpacamara\b", re.I)),
    (Variety.MARAGOGIPE, re.compile(r"\bmaragogipe\b|\bmaragogype\b", re.I)),
    (Variety.MOKKA, re.compile(r"\bmokka\b", re.I)),
    (Variety.MOKKITA, re.compile(r"\bmokkita\b", re.I)),
    (Variety.RUIRU, re.compile(r"\bruiru\b", re.I)),
    (Variety.CASTILLO, re.compile(r"\bcastillo\b", re.I)),
    (Variety.JAVA, re.compile(r"\bjava\b", re.I)),
]


def _joined_terms(terms: list[str]) -> str:
    return " ; ".join(term.strip() for term in terms if term and term.strip().lower() != UNKNOWN)


def map_process_terms(terms: list[str]) -> list[ProcessMethod]:
    text = _joined_terms(terms)
    labels = [label for label, pattern in _PROCESS_VOCAB_PATTERNS if pattern.search(text)]
    return labels or [ProcessMethod.UNKNOWN]


def map_variety_terms(terms: list[str]) -> list[Variety]:
    text = _joined_terms(terms)
    labels = [label for label, pattern in _VARIETY_VOCAB_PATTERNS if pattern.search(text)]
    return labels or [Variety.UNKNOWN]


def bool_label(value: bool) -> str:
    return "1" if value else "0"


def to_model_input(coffee: ExtractedCoffee, price: ExtractedPrice) -> ModelInput:
    return ModelInput(
        origin_country=coffee.origin_country,
        process_method=joined_model_labels(map_process_terms(coffee.process_method)),
        variety=joined_model_labels(map_variety_terms(coffee.variety)),
        is_blend=bool_label(coffee.is_blend),
        is_espresso=bool_label(coffee.is_espresso),
        is_decaf=bool_label(coffee.is_decaf),
        producer_or_farm_present=bool_label(bool(coffee.producer_or_farm)),
        altitude_present=bool_label(bool(coffee.altitude)),
        roaster_country=coffee.roaster_country,
        sensory_text=coffee.sensory_text,
        producer_text=coffee.producer_text,
        package_grams=price.package_grams,
    )
