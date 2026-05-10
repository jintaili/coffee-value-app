from __future__ import annotations

from enum import StrEnum
from typing import Literal

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
    """Human-facing extraction result from a product page."""

    model_config = ConfigDict(extra="forbid")

    coffee_name: str | None
    roaster: str | None
    roaster_location: str | None
    roaster_country: str
    origin_country: str
    origin_region: str
    process_method: list[ProcessMethod]
    variety: list[Variety]
    producer_or_farm: str | None
    altitude: str | None
    is_blend: bool
    is_espresso: bool
    is_decaf: bool
    sensory_text: str
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
        if len(self.process_method) > 1 and ProcessMethod.UNKNOWN in self.process_method:
            self.process_method = [v for v in self.process_method if v != ProcessMethod.UNKNOWN]
        if len(self.variety) > 1 and Variety.UNKNOWN in self.variety:
            self.variety = [v for v in self.variety if v != Variety.UNKNOWN]
        return self


class ExtractedPrice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listed_price: float | None = Field(ge=0)
    listed_currency: str | None
    original_listed_price: float | None = Field(default=None, ge=0)
    original_listed_currency: str | None = None
    currency_conversion_status: Literal["not_attempted", "not_needed", "converted", "missing_data", "failed"] = (
        "not_attempted"
    )
    currency_conversion_rate: float | None = Field(default=None, gt=0)
    currency_conversion_date: str | None = None
    bag_size_value: float | None = Field(gt=0)
    bag_size_unit: Literal["g", "kg", "oz", "lb"] | None
    package_grams: float | None = Field(gt=0)
    price_100g_usd: float | None = Field(gt=0)
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


class PageExtraction(BaseModel):
    """Structured output expected from the LLM extractor."""

    model_config = ConfigDict(extra="forbid")

    coffee: ExtractedCoffee
    price: ExtractedPrice
    quality: QualityReport


class AnalyzeResponse(BaseModel):
    api_version: Literal["v1"] = "v1"
    status: Literal["ok"] = "ok"
    input: AnalyzeRequest
    coffee: ExtractedCoffee
    price: ExtractedPrice
    model_input: ModelInput
    prediction: PredictionResult
    quality: QualityReport


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


def bool_label(value: bool) -> str:
    return "1" if value else "0"


def to_model_input(coffee: ExtractedCoffee, price: ExtractedPrice) -> ModelInput:
    return ModelInput(
        origin_country=coffee.origin_country,
        process_method=joined_model_labels(coffee.process_method),
        variety=joined_model_labels(coffee.variety),
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
