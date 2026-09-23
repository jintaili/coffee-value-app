"""Complete product-page extraction with shared JEV judgments and copied source values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import anyio
from bs4 import BeautifulSoup

from coffee_value.extraction.client import ProviderError, evaluate
from coffee_value.extraction.encoding import validate as validate_jev_record
from coffee_value.extraction.questions import CONTRACT_VERSION, MODEL, QUESTIONS, question_hash
from coffee_value_app.extractor import ExtractionError, ExtractionUnavailableError, trim_page_text
from coffee_value_app.product_data import (
    ProductVariant,
    choose_default_variant,
    extract_product_variants,
    parse_grams_from_text,
    selected_variant_from_url,
)
from coffee_value_app.schemas import (
    UNKNOWN,
    ExtractedCoffee,
    ExtractedPrice,
    PageExtraction,
    QualityReport,
    SourceSnippet,
)


MAX_JEV_TEXT_CHARS = 12_000
MAX_CANDIDATES = 10
LABELS = r"Tastes? Like|Tasting Notes?|Flavor Notes?|Origin|Region|Variety|Producer|Farm|Estate|Elevation|Altitude|Process|Processing|Roast|Harvest"
PAGE_QUESTIONS = {
    "page_type": {
        "type": "choice",
        "instructions": (
            "Classify the product named in `bean` and the URL. A rotating subscription, assortment, "
            "or page without one identifiable roasted-coffee product is not coffee_product. "
            "Ignore related products and educational copy."
        ),
        "criteria": {
            "coffee_product": "One identifiable roasted coffee offered for sale.",
            "coffee_equipment": "A machine, grinder, filter, cup, or other coffee equipment.",
            "other_product": "A subscription, changing assortment, or another product rather than one coffee lot.",
            "not_a_product_page": "A collection, article, homepage, or page with no product for sale.",
        },
    },
    "price_type": {
        "type": "choice",
        "instructions": "What type of listed price applies to the selected product variant? Prefer a one-time purchase when both one-time and subscription options exist.",
        "criteria": {
            "one_time": "A standard one-time purchase price is available.",
            "subscription": "Only a recurring subscription shipment price is available.",
            "membership": "The price requires membership.",
            "unknown": "The purchase type is not clear.",
        },
    },
    "availability": {
        "type": "choice",
        "instructions": "What is the current availability of the product named in `bean`? Ignore related products and historical lots.",
        "criteria": {
            "in_stock": "The product can currently be added to cart or bought.",
            "sold_out": "The product is sold out, unavailable, or no longer offered.",
            "preorder": "The product is available only as a preorder.",
            "unknown": "Availability is not clear.",
        },
    },
}


@dataclass(frozen=True)
class JevExtractionResult:
    page: PageExtraction
    record: dict


def _name_and_roaster(html: str, url: str) -> tuple[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    name = heading.get_text(" ", strip=True) if heading else ""
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    words = name.split()
    if words and sum(len(word) == 1 for word in words) > len(words) / 2:
        name = re.split(r"\s+[|–—-]\s+", title)[0].strip()
    if not name:
        name = re.split(r"\s+[|–—-]\s+", title)[0].strip()
    site = soup.find("meta", attrs={"property": "og:site_name"})
    roaster = str(site.get("content") or "").strip() if site else ""
    if not roaster:
        parts = re.split(r"\s+[|–—]\s+", title)
        roaster = parts[-1].strip() if len(parts) > 1 else ""
    if not roaster:
        roaster = (urlparse(url).hostname or "").removeprefix("www.").split(".")[0]
    return name[:180], roaster[:120] or None


def _product_focus(page_text: str) -> str:
    """Keep the current product header and summary, not long shop-wide explainers."""
    text = page_text.split("Embedded product variant data:")[0]
    lines = text.splitlines()
    marker = next((i for i, line in enumerate(lines) if line.strip() == "Hover over each feature to learn more."), None)
    if marker is not None:
        header = lines[:marker]
        abstract = [line for line in lines[marker + 1:marker + 8] if len(line.strip()) > 80][:1]
        return trim_page_text("\n".join(header + abstract), MAX_JEV_TEXT_CHARS)
    return trim_page_text(text, MAX_JEV_TEXT_CHARS)


def _short_tasting_notes(product_text: str) -> str:
    labeled = _field(product_text, "Tastes Like", "Tasting Notes", "Flavor Notes")
    if labeled:
        value = re.sub(r"^Description:\s*", "", labeled, flags=re.I)
        value = re.split(r"\s+(?:Origin|Variety|Producer|Process):", value, maxsplit=1, flags=re.I)[0]
        if len(value) <= 120:
            return value.strip(" .;,-")
    lines = [line.strip() for line in product_text.splitlines()]
    for i, line in enumerate(lines):
        if line == "Traditional" and "PREFERRED EXTRACTION" in lines[i:i + 10]:
            items = [part for part in lines[max(0, i - 7):i]
                     if 2 <= len(part) <= 30 and len(part.split()) <= 3
                     and part not in {"Round", "Light", "Modern", "Gesha"}]
            if 2 <= len(items) <= 6:
                return ", ".join(items)
    return ""


def _field(text: str, *labels: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    label_re = re.compile(r"^(?:" + "|".join(re.escape(label) for label in labels) + r")\s*:\s*(.*)$", re.I)
    for i, line in enumerate(lines):
        match = label_re.match(line)
        if not match:
            continue
        value = match.group(1).strip() or (lines[i + 1] if i + 1 < len(lines) else "")
        value = re.split(r"\s+(?:" + LABELS + r")\s*:\s*", value, maxsplit=1, flags=re.I)[0]
        value = re.split(r"[\n\r]", value, maxsplit=1)[0].strip(" .;,-")
        if value and len(value) <= 160:
            return value
    # Meta descriptions often place several labelled facts on one line.
    pattern = re.compile(r"\b(?:" + "|".join(re.escape(label) for label in labels) + r")\s*:\s*(.*?)\s*(?=(?:" + LABELS + r")\s*:|$)", re.I)
    for match in pattern.finditer(text[:1800]):
        value = match.group(1).strip(" .;,-")
        if value and len(value) <= 160:
            return value
    return None


def _summary_process(text: str) -> str | None:
    """Read the product-specific Onyx summary when page prose conflicts."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if line == "PROCESS METHOD" and i > 0 and "ABSTRACT" in lines[max(0, i - 12):i]:
            return lines[i - 1]
    return None


def _candidates(text: str, *, sensory: bool) -> list[str]:
    patterns = (
        (r"tastes? like|tasting notes?|flavo[u]?r notes?|in the cup|expect to taste|aroma|flavo[u]?r|acidity|mouthfeel")
        if sensory else (r"producer|farm|estate|cooperat|washing station|origin|process|harvest|lot")
    )
    found: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 500 or not re.search(patterns, line, re.I):
            continue
        if line.startswith(("Title:", "URL/domain-derived", "Use the selected_by_url")):
            continue
        snippet = line[:300]
        if snippet not in seen:
            seen.add(snippet)
            found.append(snippet)
        if len(found) >= MAX_CANDIDATES:
            break
    return found


def _source_question(kind: str, candidates: list[str]) -> dict:
    return {
        "type": "choice",
        "instructions": (
            f"Which numbered excerpt gives the most useful {kind} information for the exact product in `bean`? "
            "Select none when all excerpts describe another item, generic coffee, or no relevant facts."
        ),
        "criteria": {**{f"s{i}": candidate for i, candidate in enumerate(candidates)},
                     "none": "No candidate describes this product's requested information."},
    }


def _picked(answers: dict, key: str, candidates: list[str]) -> str:
    choice = answers.get(key, {}).get("choice", "none")
    if isinstance(choice, str) and re.fullmatch(r"s\d+", choice):
        index = int(choice[1:])
        if index < len(candidates):
            return candidates[index]
    return ""


def _listed_price(variant: ProductVariant | None, product_text: str) -> tuple[float | None, str | None, float | None, str | None, float | None, int | None, list[str]]:
    assumptions: list[str] = []
    if variant:
        size = re.search(r"\b(\d+(?:\.\d+)?)\s*(oz|g|kg|lb)\b", variant.title, re.I)
        value = float(size.group(1)) if size else None
        unit = size.group(2).lower() if size else None
        grams = variant.grams or parse_grams_from_text(variant.title)
        count_match = re.search(r"(?:case pack|pack of)\s*\(?\s*(\d+)\s*\)?", variant.title, re.I)
        count = int(count_match.group(1)) if count_match else None
        if count and grams:
            grams *= count
        if variant.currency is None and variant.price is not None:
            assumptions.append("Embedded variant does not state a currency")
        return variant.price, variant.currency, value, unit, grams, count, assumptions
    money = re.search(r"(?:USD\s*|US\$\s*|\$\s*)(\d+(?:,\d{3})*(?:\.\d{1,2})?)", product_text[:2500], re.I)
    size = re.search(r"\b(\d+(?:\.\d+)?)\s*(oz|g|kg|lb)\b", product_text[:2500], re.I)
    price = float(money.group(1).replace(",", "")) if money else None
    currency = "USD" if money and ("USD" in money.group(0).upper() or "US$" in money.group(0).upper()) else None
    value = float(size.group(1)) if size else None
    unit = size.group(2).lower() if size else None
    grams = parse_grams_from_text(size.group(0)) if size else None
    if money or size:
        assumptions.append("No embedded variant; visible price and size require review")
    return price, currency, value, unit, grams, None, assumptions


class JevExtractor:
    def __init__(self, *, evaluate_fn: Callable = evaluate) -> None:
        self.evaluate_fn = evaluate_fn

    async def extract(self, *, url: str, page_text: str, html: str) -> JevExtractionResult:
        if not page_text.strip():
            raise ExtractionError("Cannot extract coffee details from an empty page")
        name, roaster = _name_and_roaster(html, url)
        product_text = _product_focus(page_text)
        origin = _field(product_text, "Origin", "Country") or ""
        sensory_candidates = _candidates(product_text, sensory=True)
        producer_candidates = _candidates(product_text, sensory=False)
        variants = extract_product_variants(html)
        variant = choose_default_variant(variants, selected_variant_from_url(url))
        variant_text = (
            f"Selected product variant: {variant.title}; price {variant.price} {variant.currency}; "
            f"package {variant.grams} grams."
            if variant else "No embedded product variant was found."
        )
        state = {"bean": name, "location": roaster or "", "origin": origin,
                 "blind_assessment": "", "notes": product_text, "bottom_line": "",
                 "selected_variant": variant_text, "url": url}
        questions = {**QUESTIONS, **PAGE_QUESTIONS}
        if sensory_candidates:
            questions["sensory_source"] = _source_question("tasting-note", sensory_candidates)
        if producer_candidates:
            questions["producer_source"] = _source_question("producer and origin", producer_candidates)
        try:
            response, _, _ = await anyio.to_thread.run_sync(
                lambda: self.evaluate_fn(state, questions=questions, model=MODEL, timeout=35, attempts=2)
            )
        except ProviderError as exc:
            raise ExtractionUnavailableError(f"JEV extraction is unavailable: {exc}") from exc
        if response.get("model") != MODEL or not isinstance(response.get("answers"), dict):
            raise ExtractionError("JEV returned a mismatched model or incomplete answers")
        answers = response["answers"]
        if not set(questions) <= set(answers):
            raise ExtractionError("JEV omitted a required extraction answer")
        record = {"status": "complete", "contract_version": CONTRACT_VERSION,
                  "question_hash": question_hash(), "requested_model": MODEL, "resolved_model": MODEL,
                  "answers": {qid: answers[qid] for qid in QUESTIONS}}
        try:
            validate_jev_record(record)
        except ValueError as exc:
            raise ExtractionError("JEV returned an invalid feature record") from exc
        page = self._to_page(name, roaster, product_text, origin, variant, answers,
                             sensory_candidates, producer_candidates)
        return JevExtractionResult(page=page, record=record)

    @staticmethod
    def _to_page(name: str, roaster: str | None, product_text: str, origin: str,
                 variant: ProductVariant | None, answers: dict, sensory_candidates: list[str],
                 producer_candidates: list[str]) -> PageExtraction:
        page_type = answers["page_type"]["choice"]
        if page_type not in {"coffee_product", "coffee_equipment", "other_product", "not_a_product_page"}:
            raise ExtractionError("JEV returned an invalid page type")
        if page_type != "coffee_product":
            return PageExtraction(
                page_type=page_type, is_specialty_coffee=None,
                coffee=ExtractedCoffee(coffee_name=name or None, roaster=roaster, roaster_location=None,
                    roaster_country=UNKNOWN, origin_country=UNKNOWN, origin_region=UNKNOWN,
                    process_method=[UNKNOWN], variety=[UNKNOWN], producer_or_farm=None, altitude=None,
                    is_blend=False, is_espresso=False, is_decaf=False, sensory_text="",
                    producer_text="", source_snippets=[]),
                price=ExtractedPrice(listed_price=None, listed_currency=None, bag_size_value=None,
                    bag_size_unit=None, package_grams=None, price_100g_usd=None, assumptions=[]),
                quality=QualityReport(extraction_quality="poor", missing_fields=[],
                    warnings=["No single roasted-coffee product to appraise"]),
            )

        def supported(key: str, threshold: float = 0.75) -> bool:
            answer = answers[key]
            return answer["choice"] == "supported" and answer["probabilities"].get("supported", 0) >= threshold

        origin_choice = answers["origin_country"]["choice"]
        origin_country = ("blend_multi_origin" if origin_choice == "multiple_countries" else origin_choice)
        if origin_country in {"other", "not_stated", "conflicting"}:
            origin_country = UNKNOWN
        roaster_choice = answers["roaster_country"]["choice"]
        roaster_country = roaster_choice if roaster_choice not in {"other", "not_stated", "conflicting"} else UNKNOWN
        process = [label for label in ("washed", "natural", "honey", "anaerobic", "carbonic_maceration", "wet_hulled", "lactic")
                   if supported(f"process_{label}", 0.60)]
        summary_process = _summary_process(product_text)
        if not process and summary_process:
            process = [method for method in ("washed", "natural", "honey", "anaerobic")
                       if re.search(rf"\b{method}\b", summary_process, re.I)]
        varieties = [label.replace("_", " ") for label in ("gesha", "pink_bourbon", "bourbon", "typica", "caturra", "catuai",
                     "sl28", "sl34", "pacamara", "maragogipe", "mokka", "mokkita", "ruiru", "castillo", "java")
                     if supported(f"variety_{label}")]
        sensory = _picked(answers, "sensory_source", sensory_candidates)
        if not sensory:
            sensory = _field(product_text, "Tastes Like", "Tasting Notes", "Flavor Notes") or ""
        producer = _field(product_text, "Producer", "Farm", "Estate") if supported("producer_identified") else None
        producer_text = _picked(answers, "producer_source", producer_candidates)
        altitude = _field(product_text, "Elevation", "Altitude") if supported("altitude_provided") else None
        region = origin.strip()
        if origin_country != UNKNOWN:
            region = re.sub(rf"(?:,\s*)?{re.escape(origin_country)}\s*$", "", region, flags=re.I).strip(" ,")
        price, currency, size_value, size_unit, grams, count, assumptions = _listed_price(variant, product_text)
        if currency is None and price is not None and re.search(r"\$\s*\d|USD", product_text[:2500], re.I):
            currency = "USD"
            assumptions.append("USD inferred from page price label")
        price_100g = price / grams * 100 if price is not None and currency == "USD" and grams else None
        notes = _short_tasting_notes(product_text)
        snippets = []
        for field, value in (("origin", origin), ("process", summary_process or _field(product_text, "Process", "Processing")),
                             ("variety", _field(product_text, "Variety")), ("tasting_notes", sensory),
                             ("producer", producer), ("altitude", altitude)):
            if value:
                snippets.append(SourceSnippet(field=field, snippet=value[:250]))
        if variant:
            snippets.append(SourceSnippet(field="price", snippet=f"{variant.title}: {variant.price} {variant.currency}"))
        missing = [field for field, value in (("origin_country", origin_country if origin_country != UNKNOWN else None),
                   ("process_method", process), ("variety", varieties), ("price", price),
                   ("package_grams", grams)) if not value]
        warnings = []
        if variant is None:
            warnings.append("Price and package size were read from visible text without embedded variant data")
        if answers["origin_country"]["choice"] == "conflicting":
            warnings.append("Conflicting origin claims")
        if any(answers[f"process_{label}"]["choice"] == "conflicting" for label in
               ("washed", "natural", "honey", "anaerobic", "carbonic_maceration", "wet_hulled", "lactic")):
            warnings.append("Conflicting process claims on the product page")
        quality = "good" if len(missing) <= 1 and sensory and price is not None else "partial" if len(missing) <= 3 else "poor"
        return PageExtraction(
            page_type="coffee_product",
            is_specialty_coffee=bool(origin_country != UNKNOWN and (process or varieties)),
            coffee=ExtractedCoffee(
                coffee_name=name or None, roaster=roaster, roaster_location=None,
                roaster_country=roaster_country, origin_country=origin_country,
                origin_region=region or UNKNOWN, process_method=process or [UNKNOWN],
                variety=varieties or [UNKNOWN], producer_or_farm=producer, altitude=altitude,
                is_blend=supported("blend") or origin_country == "blend_multi_origin",
                is_espresso=answers["brewing_intent"]["choice"] == "espresso_primary",
                is_decaf=supported("decaf"), sensory_text=sensory,
                display_tasting_notes=notes, producer_text=producer_text,
                source_snippets=snippets,
            ),
            price=ExtractedPrice(listed_price=price, listed_currency=currency,
                bag_size_value=size_value, bag_size_unit=size_unit, package_grams=grams,
                bags_count=count, price_100g_usd=price_100g,
                price_type=answers["price_type"]["choice"],
                availability=answers["availability"]["choice"], assumptions=assumptions),
            quality=QualityReport(extraction_quality=quality, missing_fields=missing, warnings=warnings),
        )
