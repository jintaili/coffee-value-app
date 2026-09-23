from __future__ import annotations

import argparse
import asyncio
import json
import sys

from coffee_value_app.analysis import AnalysisService
from coffee_value_app.config import load_settings
from coffee_value_app.extractor import ExtractionError
from coffee_value_app.fetcher import FetchError


def main() -> None:
    parser = argparse.ArgumentParser(prog="coffee-value")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract coffee attributes from a product URL.")
    extract_parser.add_argument("url", help="Specialty coffee product URL to analyze.")
    extract_parser.add_argument(
        "--show-text",
        action="store_true",
        help="Print the readable page text sent to the extractor before JSON output.",
    )

    args = parser.parse_args()
    if args.command == "extract":
        asyncio.run(
            run_extract(
                args.url,
                show_text=args.show_text,
            )
        )


async def run_extract(url: str, *, show_text: bool) -> None:
    try:
        settings = load_settings()
        if show_text:
            from coffee_value_app.analysis import build_page_context
            from coffee_value_app.fetcher import fetch_product_page

            page = await fetch_product_page(url)
            page_text = build_page_context(page.text, page.final_url)
            print("=== Readable Page Text ===")
            print(page_text)
            print("=== Extraction JSON ===")
        service = AnalysisService(settings=settings)
        response = await service.analyze_url(url)
    except (FetchError, ExtractionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    extraction_like = {
        "coffee": response.coffee.model_dump(mode="json"),
        "price": response.price.model_dump(mode="json"),
        "quality": response.quality.model_dump(mode="json"),
    }
    print(json.dumps(extraction_like, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
