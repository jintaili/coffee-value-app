# Worth the Roast?

[Live app](https://coffee-value-app.onrender.com/)

**Worth the Roast?** is an end-to-end inference app for specialty coffee shoppers, with machine learning rating and price models served in the backend. Paste a roaster product URL and the app extracts the coffee's production details, predicts quality and fair price, normalizes currencies and bag sizes, and returns a concise value verdict.

Portfolio highlights:

- TypeSafe JEV extraction from messy product pages using the same typed feature contract as training.
- FastAPI backend serving local machine learning artifacts for rating and fair-price prediction.
- Production-shaped normalization for package size, currency conversion, roaster country resolution, and extraction quality warnings.
- Optional Supabase/Postgres query history for saving analyzed URLs, responses, and failed attempts.
- Consumer-facing single-page UI with debug visibility into extracted JSON, source snippets, assumptions, and model versions.
- Deployment-ready Python service with tests, CLI tooling, and Render configuration.

This repo is the web application and inference layer. Model training, experiment selection, and automated coffee research workflows live in [`coffee-value-autoresearch`](https://github.com/jintaili/coffee-value-autoresearch).

## JEV case study

The live app uses TypeSafe JEV for typed product-page judgments and the selected
JEV-feature price model. The lightweight rating model remains in place. In the
research validation set, price RMSLE fell from 0.25917 to 0.25361, a 2.14%
relative improvement. This was exploratory validation, not a fresh test set.
On eight public pages, complete extraction took 0.423 seconds at the median with
JEV versus 4.879 seconds with the previous extractor, a 91.3% reduction across
16 local pairs. Page fetch and prediction were excluded; production end-to-end
latency has not been measured.
Read the [results and limitations](https://coffee-value-app.onrender.com/static/jev/jev-results-showcase.html)
or the [reproduction instructions](https://github.com/jintaili/coffee-value-autoresearch#jev-case-study).

## What It Does

The app answers a narrow product question:

> Is this specialty coffee likely good, and is the listed price fair for the predicted quality?

A request flows through:

1. Fetch a public specialty coffee product page.
2. Convert HTML and embedded product data into model-readable page context.
3. Ask JEV the same typed feature questions used for training, plus page and source-selection questions. Copy exact prices and package sizes from the product page.
4. Infer roaster country from the domain when useful and normalize non-USD prices to USD.
5. Run the lightweight rating model and JEV-feature price model locally.
6. Return a value verdict plus inspectable extraction and prediction details.

## Core Components

- `src/coffee_value_app/main.py`: FastAPI app, health check, static UI, and `/api/analyze`.
- `src/coffee_value_app/analysis.py`: orchestration for fetch, extraction, normalization, and prediction.
- `src/coffee_value_app/jev_extractor.py`: live JEV judgments and product-page extraction.
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
# edit .env and set TYPESAFE_API_KEY
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

- `TYPESAFE_API_KEY`: required for live JEV extraction. Keep it in an uncommitted `.env` locally and a server-side secret in Render.
- `COFFEE_VALUE_DATABASE_URL`: optional Postgres connection string for query history. Use the Supabase pooled connection string in production. If unset, the app runs normally with history disabled.

See `.env.example` for the current defaults.

## Query History

When `COFFEE_VALUE_DATABASE_URL` or `DATABASE_URL` is set, the API records each `/api/analyze` request in a Postgres `query_history` table. The app creates the table and index on first use, stores compact JSON analysis results, and exposes recent entries at:

```bash
curl http://127.0.0.1:8000/api/history
```

For Supabase, keep the connection string server-side in Render environment variables. Do not expose service-role credentials or database URLs in browser JavaScript.

## Currency Conversion

Non-USD extracted prices are normalized to USD before prediction using Frankfurter's public exchange-rate API. Rates are cached in memory for 12 hours, and conversion assumptions are returned in the analysis response. If conversion fails, the original price is preserved and value prediction remains unavailable for that item.

## Deployment

The repo includes `render.yaml` for a Render web service:

```bash
python -m pip install .
uvicorn coffee_value_app.main:app --host 0.0.0.0 --port $PORT
```

The `lightweight` branch ships the selected JEV-feature ElasticNet price artifact alongside the TF-IDF/ridge rating artifact. It has no sentence-transformer or Torch runtime dependency. Regenerate the price artifact with `python -m scripts.export_jev_price_for_app --destination ../coffee-value-app/artifacts/price/jev_pg.pkl` from the research repo.

## Companion Repo

[`coffee-value-autoresearch`](https://github.com/jintaili/coffee-value-autoresearch) contains the model research pipeline, experiment ledgers, selected model notes, shared feature contract, and automated coffee research workflows that complement this inference app.
