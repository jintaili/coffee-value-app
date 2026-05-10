# Coffee Value App PRD

## Purpose

Build a web app that helps a user evaluate a specialty coffee product page. A user submits a roaster product URL, the app extracts coffee attributes from the page, runs rating and price inference, and presents a concise value judgment.

This repo covers the inference web app, not model training. The trained rating and price models are assumed to arrive later as serialized artifacts with a stable input schema.

## Product Goal

Answer the user's core question:

> Is this coffee likely good, and is the listed price fair?

The app should be useful even before final models are available by implementing the URL fetch, extraction, normalization, validation, UI, persistence, and model-service boundary with deterministic placeholder predictions.

## Target User

- Specialty coffee buyers comparing roaster listings.
- Hobbyists who understand origin, process, and variety but want a quick second opinion.
- The initial user is technical enough to inspect debug details, but the default UI should remain consumer-friendly.

## User Flow

The app should be a single-page workflow.

1. User enters a specialty coffee product URL.
2. App fetches and extracts readable page content.
3. App extracts structured coffee attributes.
4. App displays a coffee summary and extraction warnings.
5. App runs rating and price inference.
6. App displays predicted rating, predicted fair price, and a value verdict.
7. User can expand details to inspect raw extracted JSON, warnings, assumptions, and model versions.

## UX Requirements

### Initial State

- A single URL input.
- One clear analyze action.
- Short placeholder text indicating that roaster product pages are expected.

### Loading State

Show progress through major stages:

- Fetching page
- Extracting coffee details
- Running prediction

### Result State

The main result should be organized into four sections:

#### Coffee Summary

Visible attributes:

- Coffee name
- Roaster
- Origin country and region
- Process method
- Variety
- Producer, farm, station, cooperative, or mill when present
- Altitude when present
- Tasting notes or short sensory summary
- Listed price
- Bag size
- Normalized listed price, such as `USD / 100g`

Use badges for notable flags:

- Blend
- Espresso
- Decaf

Do not show false boolean flags by default.

#### Prediction

Primary outputs:

- Predicted rating
- Predicted rating interval when available
- Predicted fair price for the listed bag size
- Predicted fair price normalized to `price_100g_usd`
- Predicted price interval when available

Avoid false precision. If model error supports only whole-point ratings, display whole-point ratings.

#### Value Verdict

Display a human-readable interpretation:

- Good value
- Priced about right
- Expensive for predicted quality
- High-quality but premium priced
- Insufficient information

The verdict should be derived from predicted rating, predicted fair price, listed price, and extraction quality.

#### Warnings and Assumptions

Show concise warnings when extraction is incomplete or uncertain:

- Could not find bag size
- Could not find listed price
- Multiple prices found
- Origin unclear
- Process method unknown
- Variety unknown
- Prediction may be less reliable because key fields are missing

### Details Panel

Collapsed by default. Include:

- Raw extracted JSON
- Raw page snippets used for extraction
- Missing fields
- Extraction confidence or completeness score
- Model artifact versions
- API response version

## Canonical Extracted Attributes

The app should extract and validate fields aligned with the model-training schema.

### Product Identity

- `product_url`
- `coffee_name`
- `roaster`
- `roaster_location`
- `roaster_country`

### Coffee Attributes

- `origin_country`
- `origin_region`
- `process_method`
- `variety`
- `producer_or_farm`
- `altitude`
- `is_blend`
- `is_espresso`
- `is_decaf`

### Text Fields

- `sensory_text`
- `producer_text`
- `page_title`
- `page_description`

### Price Fields

- `listed_price`
- `listed_currency`
- `bag_size_value`
- `bag_size_unit`
- `price_100g_usd`
- `price_parse_assumptions`

### Quality and Provenance

- `extraction_warnings`
- `missing_fields`
- `source_snippets`
- `extractor_version`

## API Requirements

### `POST /api/analyze`

Request:

```json
{
  "url": "https://example-roaster.com/products/example-coffee"
}
```

Response:

```json
{
  "api_version": "v1",
  "status": "ok",
  "input": {
    "url": "https://example-roaster.com/products/example-coffee"
  },
  "coffee": {
    "coffee_name": "Example Coffee",
    "roaster": "Example Roaster",
    "origin_country": "Kenya",
    "origin_region": "Nyeri",
    "process_method": ["washed"],
    "variety": ["sl28", "sl34"],
    "producer_or_farm": "Example Cooperative",
    "altitude": "1800-2000 masl",
    "is_blend": false,
    "is_espresso": false,
    "is_decaf": false,
    "sensory_text": "Blackcurrant, citrus, florals.",
    "producer_text": "Washed coffee from Nyeri..."
  },
  "price": {
    "listed_price": 23.0,
    "listed_currency": "USD",
    "bag_size_value": 250,
    "bag_size_unit": "g",
    "price_100g_usd": 9.2,
    "assumptions": []
  },
  "prediction": {
    "rating": {
      "predicted": 93,
      "interval_low": null,
      "interval_high": null,
      "model_version": "stub"
    },
    "price": {
      "predicted_price_100g_usd": 8.5,
      "predicted_bag_price_usd": 21.25,
      "interval_low": null,
      "interval_high": null,
      "model_version": "stub"
    },
    "value": {
      "verdict": "Priced about right",
      "listed_vs_predicted_delta_pct": 8.2
    }
  },
  "quality": {
    "extraction_quality": "good",
    "missing_fields": [],
    "warnings": []
  }
}
```

### Error Responses

Support structured errors for:

- Invalid URL
- Unsupported URL scheme
- URL blocked for safety
- Fetch timeout
- Page too large
- Could not extract meaningful text
- LLM extraction failed
- Schema validation failed
- Inference failed

## Backend Requirements

### Safe URL Fetching

The backend must:

- Allow only `http` and `https`.
- Reject localhost and private-network destinations.
- Limit redirects.
- Set a request timeout.
- Limit downloaded body size.
- Use a clear user agent.
- Extract readable text from HTML.

### Feature Extraction

The extractor should be replaceable and testable.

Initial implementation may use:

- A mock extractor for development and tests.
- An LLM extractor for live analysis.

The extractor must:

- Return strict JSON matching the app schema.
- Prefer `unknown` or `null` over guessed values.
- Include source snippets for key extracted fields when possible.
- Produce warnings for ambiguous or missing fields.

### Price Normalization

The app should parse:

- Currency
- Listed price
- Bag size
- Unit

Supported units:

- `g`
- `kg`
- `oz`
- `lb`

The normalized model-facing value is:

- `price_100g_usd`

For v1, assume USD when a US roaster page uses `$` and no other currency is found. Record that assumption.

### Model Service

Define a stable model service interface:

- `predict_rating(features)`
- `predict_price(features)`

Until trained artifacts are available, use deterministic stub predictions.

The final model service should:

- Load serialized artifacts at process startup.
- Use the same preprocessing as training.
- Return model version metadata.
- Return prediction intervals if the trained model provides calibrated uncertainty.

## Persistence Requirements

Store each analysis request and result.

Minimum fields:

- URL
- Extracted features JSON
- Prediction JSON
- Warnings
- Extractor version
- Model versions
- Created timestamp

Local development may use SQLite. Hosted deployment should use Postgres if results need to persist.

## Testing Requirements

Create a small fixture set of real or saved product pages.

Tests should cover:

- URL validation and blocked destinations
- HTML-to-text extraction
- Schema validation
- Price normalization
- Value verdict logic
- Model stub determinism
- API response shape

Add golden extraction fixtures for 10-20 product pages once representative examples are selected.

## Hosting Recommendation

Use Render for the first deployed version.

Recommended setup:

- Backend: FastAPI web service on Render
- Frontend: static site on Render, or Vercel if using Next.js
- Database: Render Postgres for durable hosted data
- LLM: external API
- Model artifacts: bundled with backend if small, object storage if large

Render is preferred for the backend because this app is a conventional Python service that may load ML artifacts and dependencies at startup.

## Non-Goals for V1

- User accounts
- Payments
- Browser extension
- Mobile app
- Full historical price tracking
- Training models inside this repo
- Self-hosting LLMs
- Complex model explainability
- Multi-coffee comparison tables

## Open Decisions

- Whether inference should run immediately after extraction or after a user review step.
- Which LLM provider and model to use for extraction.
- Whether users can edit extracted attributes before inference.
- How to calibrate and display prediction intervals.
- Whether saved analyses should be public, private, or local-only.
- Whether to cache URL fetches and LLM extraction results.
- How aggressive the app should be when inferring missing bag sizes.

## Suggested Implementation Order

1. Backend skeleton with health check.
2. Shared schema definitions.
3. Safe URL validation and fetching.
4. HTML-to-text extraction.
5. Mock extractor.
6. Price parser and normalizer.
7. Model service stub.
8. `POST /api/analyze`.
9. Single-page frontend.
10. Persistence.
11. LLM extractor.
12. Render deployment.
13. Golden fixture tests.
14. Replace model stubs with trained artifacts.
