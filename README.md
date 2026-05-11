# Worth the Roast?

[Live app](https://coffee-value-app.onrender.com/)

**Worth the Roast?** is an end-to-end inference app for specialty coffee shoppers, with machine learning rating and price models served in the backend. Paste a roaster product URL and the app extracts the coffee's production details, predicts quality and fair price, normalizes currencies and bag sizes, and returns a concise value verdict.

Portfolio highlights:

- LLM-powered structured extraction from messy real-world product pages, aligned to downstream ML feature schemas.
- FastAPI backend serving local machine learning artifacts for rating and fair-price prediction.
- Production-shaped normalization for package size, currency conversion, roaster country resolution, and extraction quality warnings.
- Consumer-facing single-page UI with debug visibility into extracted JSON, source snippets, assumptions, and model versions.
- Deployment-ready Python service with tests, CLI tooling, and Render configuration.

This repo is the web application and inference layer. Model training and experiment selection live in the companion `coffee-grader` repo.

## What It Does

The app answers a narrow product question:

> Is this specialty coffee likely good, and is the listed price fair for the predicted quality?

A request flows through:

1. Fetch a public specialty coffee product page.
2. Convert HTML and embedded product data into model-readable page context.
3. Use an OpenAI structured-output extractor to produce the exact fields needed by the models.
4. Resolve missing roaster country when useful and normalize non-USD prices to USD.
5. Run local rating and price model artifacts.
6. Return a value verdict plus inspectable extraction and prediction details.

## Core Components

- `src/coffee_value_app/main.py`: FastAPI app, health check, static UI, and `/api/analyze`.
- `src/coffee_value_app/analysis.py`: orchestration for fetch, extraction, normalization, and prediction.
- `src/coffee_value_app/extractor.py`: OpenAI structured-output extraction prompt and parser.
- `src/coffee_value_app/model_runtime.py`: local model artifact loading and prediction.
- `src/coffee_value_app/currency.py`: real-time currency normalization through Frankfurter.
- `static/`: single-page UI for URL analysis, value verdict, summary fields, and debug panels.
- `tests/`: API, extraction, schema, currency, UI, and runtime coverage.

## Development

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Configure live extraction:

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

Run the API:

```bash
uvicorn coffee_value_app.main:app --reload
```

Open the app at:

```text
http://127.0.0.1:8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Run the test suite:

```bash
pytest
```

## CLI Extraction

Run extraction from a product URL:

```bash
coffee-value extract "https://onyxcoffeelab.com/products/peru-la-margarita-gesha-26?variant=42842298646626"
```

Override the extraction model:

```bash
coffee-value extract "https://example.com/product" --model gpt-4o-mini
```

## API

Analyze a product page:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url":"https://hydrangea.coffee/products/salma-bermudez"}'
```

The response includes:

- `coffee`: extracted production and sensory fields.
- `price`: listed price, package size, normalized USD price per 100g, and assumptions.
- `model_input`: the canonical feature row passed to the predictors.
- `prediction`: rating, fair price, intervals, model versions, and value verdict.
- `quality`: missing fields, warnings, source snippets, and extraction quality.

## Configuration

Environment variables are loaded from `.env` in development:

- `OPENAI_API_KEY`: required for live extraction.
- `OPENAI_EXTRACTION_MODEL`: structured extraction model.
- `OPENAI_WEB_SEARCH_MODEL`: optional roaster-country resolver model.
- `MAX_PAGE_TEXT_CHARS`: page-context budget sent to the extractor.

See `.env.example` for the current defaults.

## Currency Conversion

Non-USD extracted prices are normalized to USD before prediction using Frankfurter's public exchange-rate API. Rates are cached in memory for 12 hours, and conversion assumptions are returned in the analysis response. If conversion fails, the original price is preserved and value prediction remains unavailable for that item.

## Deployment

The repo includes `render.yaml` for a Render web service:

```bash
python -m pip install .
uvicorn coffee_value_app.main:app --host 0.0.0.0 --port $PORT
```

The `lightweight` branch scales back the backend models for easier deployment: TF-IDF/ridge rating inference and ElasticNet price inference, with no sentence-transformer or Torch runtime dependency.

## Companion Repo

`coffee-grader` contains the model research pipeline, experiment ledgers, selected model notes, and shared feature contract used by this app.
