# Coffee Value App

Web app for analyzing specialty coffee product pages and estimating rating, fair price, and value.

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

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Run extraction from a product URL:

```bash
coffee-value extract "https://onyxcoffeelab.com/products/peru-la-margarita-gesha-26?variant=42842298646626"
```

Override the extraction model:

```bash
coffee-value extract "https://example.com/product" --model gpt-4o-mini
```

## Currency Conversion

Non-USD extracted prices are normalized to USD before prediction using Frankfurter's public exchange-rate API. Rates are cached in memory for 12 hours, and conversion assumptions are returned in the analysis response. If conversion fails, the original price is kept and value prediction remains unavailable for that item.
