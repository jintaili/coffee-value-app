from __future__ import annotations

import os
from typing import Protocol

from openai import AsyncOpenAI

from coffee_value_app.config import DEFAULT_EXTRACTION_MODEL, DEFAULT_MAX_PAGE_TEXT_CHARS, Settings, load_settings
from coffee_value_app.schemas import PageExtraction


MAX_PAGE_TEXT_CHARS = DEFAULT_MAX_PAGE_TEXT_CHARS


class ExtractionError(Exception):
    """Raised when coffee extraction fails."""


class ResponsesParseClient(Protocol):
    async def parse(self, **kwargs): ...


class OpenAILLMExtractor:
    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        max_page_text_chars: int = MAX_PAGE_TEXT_CHARS,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or load_settings()
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.extraction_model or DEFAULT_EXTRACTION_MODEL
        self.max_page_text_chars = max_page_text_chars

    async def extract(self, *, url: str, page_text: str) -> PageExtraction:
        trimmed_text = trim_page_text(page_text, self.max_page_text_chars)
        if not trimmed_text:
            raise ExtractionError("Cannot extract coffee details from empty page text.")

        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_extraction_user_prompt(url=url, page_text=trimmed_text),
                },
            ],
            text_format=PageExtraction,
        )
        return parse_structured_response(response)


def trim_page_text(page_text: str, max_chars: int = MAX_PAGE_TEXT_CHARS) -> str:
    text = "\n".join(line.strip() for line in page_text.splitlines() if line.strip())
    if len(text) <= max_chars:
        return text
    head_chars = int(max_chars * 0.7)
    tail_chars = max_chars - head_chars
    return (
        text[:head_chars]
        + "\n\n[... middle of page omitted for length ...]\n\n"
        + text[-tail_chars:]
    )


def parse_structured_response(response) -> PageExtraction:
    for output in getattr(response, "output", []):
        if getattr(output, "type", None) != "message":
            continue
        for item in getattr(output, "content", []):
            if getattr(item, "type", None) == "refusal":
                raise ExtractionError(getattr(item, "refusal", "Model refused extraction request."))
            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                if isinstance(parsed, PageExtraction):
                    return parsed
                return PageExtraction.model_validate(parsed)
    raise ExtractionError("Model response did not include a parsed extraction.")


def build_extraction_user_prompt(*, url: str, page_text: str) -> str:
    return f"""Product URL:
{url}

Page text:
{page_text}
"""


EXTRACTION_SYSTEM_PROMPT = """You extract specialty coffee product information from roaster product pages.

Return only fields supported by the supplied page text. Do not use outside knowledge about the roaster or coffee.
Use null for absent human-facing fields and "unknown" for absent model labels. Never guess origin, process, variety,
price, currency, or package size when the page does not support them.

The extracted fields must align with two downstream prediction models:
- Rating model inputs: origin_country, process_method, variety, is_blend, is_espresso, is_decaf,
  producer_or_farm_present, altitude_present, roaster_country, sensory_text, producer_text.
- Price model inputs: all rating inputs plus package_grams.

Extraction guidance:
- coffee_name: product coffee name, not the website title unless that is the only product name.
- roaster: company/roaster name shown on the page.
- roaster_country: country where the roaster is located. Use explicit page evidence first. If absent, use
  URL/domain-derived roaster evidence when provided; otherwise "unknown".
- origin_country: producing country. Use "blend_multi_origin" only when multiple producing countries are clearly present.
- origin_region: producing region, province, department, farm area, or "multi_origin" for multi-country blends.
- process_method: array using only washed, natural, honey, anaerobic, carbonic_maceration, wet_hulled, lactic, unknown.
  Include multiple values only if the page supports multiple methods.
- variety: array using only gesha, bourbon, typica, caturra, catuai, sl28, sl34, pacamara, maragogipe, mokka,
  mokkita, pink_bourbon, ruiru, castillo, java, unknown. Normalize geisha to gesha.
- producer_or_farm: producer, farm, estate, cooperative, mill, washing station, or family when present.
- altitude: altitude/elevation string as written or normalized, including units.
- is_blend: true only for clearly labeled blends or multiple producing origins.
- is_espresso: true only when the product is intended for espresso or espresso appears as a product/use cue.
- is_decaf: true when decaf, decaffeinated, Swiss Water, or similar decaffeination method appears.
- sensory_text: concise tasting/cup/flavor/aroma/body/acidity/finish notes. Prefer product tasting notes over marketing copy.
- producer_text: concise origin, farm, producer, process, variety, altitude, lot, and sourcing details.
- listed_price: current product price for the selected/default variant if visible.
- listed_currency: ISO-like currency code such as USD, CAD, GBP, EUR when inferable; otherwise null.
- bag_size_value and bag_size_unit: package size for the same selected/default variant as the price.
- package_grams: convert bag size to grams. Use 1 oz = 28.3495231 g and 1 lb = 453.59237 g.
- price_100g_usd: only fill when listed price is USD and package_grams is known. Otherwise null; the server will convert non-USD prices.
- assumptions: record assumptions such as "currency assumed USD from $" or "default variant selected".
- If embedded product variant data identifies a selected_by_url variant, use that variant for price and package size.
- If no selected variant is present, use the variant marked default_for_inference, chosen as the package size closest to 10 oz.
- source_snippets: include short exact snippets for important extracted fields as objects with field and snippet keys.
  Use fields like name, origin, process, variety, price, bag_size, tasting_notes, producer, altitude when available.
- missing_fields: include important fields missing for inference quality.
- warnings: include ambiguity, multiple prices, multiple variants, subscription-only price, unavailable product, or weak evidence.

Set extraction_quality to:
- "good" when origin plus several key production fields or tasting notes and package price are present.
- "partial" when the page has enough to run inference but important fields are missing.
- "poor" when the page is not a coffee product page or key fields are mostly absent.
"""
