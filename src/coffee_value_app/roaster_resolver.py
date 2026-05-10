from __future__ import annotations

import os
from typing import Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict

from coffee_value_app.config import Settings, load_settings
from coffee_value_app.schemas import UNKNOWN, ExtractedCoffee, SourceSnippet


class RoasterCountryResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roaster_country: str
    confidence: str
    evidence_url: str | None
    evidence_title: str | None
    evidence_snippet: str | None


class RoasterResolutionError(Exception):
    """Raised when live roaster country resolution fails."""


class ResponsesParseClient(Protocol):
    async def parse(self, **kwargs): ...


class OpenAIWebRoasterResolver:
    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or load_settings()
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model or settings.web_search_model

    async def resolve(self, *, roaster: str | None, url: str) -> RoasterCountryResolution:
        if not roaster:
            raise RoasterResolutionError("Cannot resolve roaster country without a roaster name.")

        response = await self.client.responses.parse(
            model=self.model,
            tools=[{"type": "web_search", "search_context_size": "low"}],
            tool_choice="required",
            input=[
                {
                    "role": "system",
                    "content": (
                        "Resolve the country where a specialty coffee roaster is based. "
                        "Use web search. Return unknown unless the searched evidence clearly identifies "
                        "the roaster/company location or headquarters country. Do not infer from TLD alone."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Roaster name: {roaster}\n"
                        f"Product URL/domain: {url}\n"
                        "Find the country where this roaster is based."
                    ),
                },
            ],
            text_format=RoasterCountryResolution,
        )
        return parse_resolution_response(response)


def parse_resolution_response(response) -> RoasterCountryResolution:
    for output in getattr(response, "output", []):
        if getattr(output, "type", None) != "message":
            continue
        for item in getattr(output, "content", []):
            if getattr(item, "type", None) == "refusal":
                raise RoasterResolutionError(getattr(item, "refusal", "Model refused roaster resolution."))
            parsed = getattr(item, "parsed", None)
            if parsed is not None:
                if isinstance(parsed, RoasterCountryResolution):
                    return parsed
                return RoasterCountryResolution.model_validate(parsed)
    raise RoasterResolutionError("Model response did not include parsed roaster resolution.")


def apply_roaster_country_resolution(
    coffee: ExtractedCoffee,
    resolution: RoasterCountryResolution,
) -> ExtractedCoffee:
    if not resolution.roaster_country or resolution.roaster_country == UNKNOWN:
        return coffee
    snippets = list(coffee.source_snippets)
    if resolution.evidence_snippet:
        snippets.append(
            SourceSnippet(
                field="roaster_country",
                snippet=resolution.evidence_snippet,
            )
        )
    return coffee.model_copy(
        update={
            "roaster_country": resolution.roaster_country,
            "source_snippets": snippets,
        }
    )

