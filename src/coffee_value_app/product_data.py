from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


TARGET_DEFAULT_GRAMS = 10 * 28.3495231


@dataclass(frozen=True)
class ProductVariant:
    id: str | None
    title: str
    name: str
    price: float | None
    currency: str | None
    grams: float | None
    sku: str | None


def embedded_product_data_to_text(html: str, url: str) -> str:
    variants = extract_product_variants(html)
    if not variants:
        return ""

    selected_variant_id = selected_variant_from_url(url)
    default_variant = choose_default_variant(variants, selected_variant_id)
    lines = ["Embedded product variant data:"]
    for variant in variants:
        markers = []
        if selected_variant_id and variant.id == selected_variant_id:
            markers.append("selected_by_url")
        if variant == default_variant:
            markers.append("default_for_inference")
        marker_text = f" [{' '.join(markers)}]" if markers else ""
        price_text = format_price(variant.price, variant.currency)
        grams_text = f"{variant.grams:.3f}g" if variant.grams else "unknown grams"
        lines.append(
            "- "
            f"id={variant.id or 'unknown'}; "
            f"title={variant.title or 'unknown'}; "
            f"name={variant.name or 'unknown'}; "
            f"sku={variant.sku or 'unknown'}; "
            f"price={price_text}; "
            f"package_grams={grams_text}"
            f"{marker_text}"
        )
    lines.append(
        "Use the selected_by_url variant when present. Otherwise use the default_for_inference variant, "
        "chosen as the package size closest to 10 oz."
    )
    return "\n".join(lines)


def extract_product_variants(html: str) -> list[ProductVariant]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[dict] = []
    page_currency = extract_page_currency(soup)

    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if script.get("type") == "application/ld+json":
            candidates.extend(extract_json_ld_products(text))
        if "variants" in text and "price" in text:
            for candidate in extract_json_assignments(text, "meta"):
                if page_currency and isinstance(candidate.get("product"), dict):
                    candidate["product"].setdefault("currency", page_currency)
                candidates.append(candidate)
            for candidate in extract_json_assignments(text, "product"):
                if page_currency:
                    candidate.setdefault("currency", page_currency)
                candidates.append(candidate)

    variants: list[ProductVariant] = []
    seen: set[tuple[str | None, str, str]] = set()
    for candidate in candidates:
        for variant in variants_from_candidate(candidate):
            key = (variant.id, variant.title, variant.name)
            if key in seen:
                continue
            seen.add(key)
            variants.append(variant)
    return variants


def extract_page_currency(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        match = re.search(r"ShopifyAnalytics\.meta\.currency\s*=\s*['\"]([A-Z]{3})['\"]", text)
        if match:
            return match.group(1)
    return None


def extract_json_ld_products(text: str) -> list[dict]:
    out = []
    for obj in parse_json_objects(text):
        if isinstance(obj, dict) and obj.get("@type") == "Product":
            out.append(obj)
    return out


def extract_json_assignments(text: str, variable_name: str) -> list[dict]:
    out = []
    for match in re.finditer(rf"\b(?:var\s+)?{re.escape(variable_name)}\s*=", text):
        start = text.find("{", match.end())
        if start == -1:
            continue
        raw = extract_balanced_object(text, start)
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def extract_balanced_object(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_json_objects(text: str) -> list[object]:
    cleaned = unescape(text).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return value
    return [value]


def variants_from_candidate(candidate: dict) -> list[ProductVariant]:
    if "product" in candidate and isinstance(candidate["product"], dict):
        candidate = candidate["product"]

    currency = candidate.get("currency") or candidate.get("priceCurrency")
    variants = candidate.get("variants")
    if isinstance(variants, list):
        return [variant_from_mapping(v, currency=currency) for v in variants if isinstance(v, dict)]

    offers = candidate.get("offers")
    if isinstance(offers, dict):
        offers = [offers]
    if isinstance(offers, list):
        return [variant_from_mapping(v, currency=currency) for v in offers if isinstance(v, dict)]
    return []


def variant_from_mapping(value: dict, *, currency: str | None) -> ProductVariant:
    title = str(value.get("public_title") or value.get("title") or value.get("name") or "").strip()
    name = str(value.get("name") or title).strip()
    sku = value.get("sku")
    raw_price = value.get("price")
    price = normalize_price(raw_price)
    resolved_currency = value.get("priceCurrency") or currency
    grams = normalize_grams(value.get("weight")) or parse_grams_from_text(" ".join([title, name, str(sku or "")]))
    return ProductVariant(
        id=str(value["id"]) if value.get("id") is not None else variant_id_from_offer_url(value.get("url")),
        title=title,
        name=name,
        price=price,
        currency=str(resolved_currency).upper() if resolved_currency else None,
        grams=grams,
        sku=str(sku) if sku else None,
    )


def normalize_price(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1000 and float(number).is_integer():
        return number / 100
    return number


def normalize_grams(value: object) -> float | None:
    if value is None:
        return None
    try:
        grams = float(value)
    except (TypeError, ValueError):
        return None
    return grams if grams > 0 else None


def parse_grams_from_text(text: str) -> float | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(oz|ounce|ounces|g|gram|grams|kg|lb|lbs|pound|pounds)\b", text, re.I)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit in {"g", "gram", "grams"}:
        return value
    if unit == "kg":
        return value * 1000
    if unit in {"oz", "ounce", "ounces"}:
        return value * 28.3495231
    if unit in {"lb", "lbs", "pound", "pounds"}:
        return value * 453.59237
    return None


def selected_variant_from_url(url: str) -> str | None:
    values = parse_qs(urlparse(url).query).get("variant")
    return values[0] if values else None


def variant_id_from_offer_url(url: object) -> str | None:
    if not isinstance(url, str):
        return None
    return selected_variant_from_url(url)


def choose_default_variant(variants: list[ProductVariant], selected_variant_id: str | None) -> ProductVariant | None:
    if selected_variant_id:
        for variant in variants:
            if variant.id == selected_variant_id:
                return variant
    variants_with_size = [variant for variant in variants if variant.grams is not None]
    if variants_with_size:
        return min(variants_with_size, key=lambda v: abs((v.grams or 0) - TARGET_DEFAULT_GRAMS))
    return variants[0] if variants else None


def format_price(price: float | None, currency: str | None) -> str:
    if price is None:
        return "unknown"
    return f"{price:.2f} {currency or 'unknown currency'}"
