from __future__ import annotations

import hashlib
import math
import pickle
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse

from coffee_value_app.schemas import (
    ExtractedPrice,
    ModelInput,
    PredictionResult,
    PricePrediction,
    RatingPrediction,
    ValuePrediction,
)


ROOT = Path(__file__).resolve().parents[2]
RATING_MODEL_PATH = ROOT / "artifacts" / "rating" / "model.pkl"
PRICE_MODEL_PATH = ROOT / "artifacts" / "price" / "model.pkl"
LOCAL_EMBEDDING_MODELS = {
    "sentence-transformers/all-MiniLM-L6-v2": ROOT / "artifacts" / "embedding_models" / "all-MiniLM-L6-v2",
}

STRUCTURED_FIELDS = [
    "origin_country",
    "process_method",
    "variety",
    "is_blend",
    "is_espresso",
    "is_decaf",
    "producer_or_farm_present",
    "altitude_present",
    "roaster_country",
]
TEXT_FIELDS = ["sensory_text", "producer_text"]
NGRAM_MAX = 2
EMBED_BATCH = 64


def tokenize(text: str) -> list[str]:
    text = (text or "").lower().replace("’", "'")
    return re.findall(r"[a-z0-9][a-z0-9'\-]*", text)


def ngrams(text: str, n_max: int = NGRAM_MAX) -> list[str]:
    toks = tokenize(text)
    grams = list(toks)
    for n in range(2, n_max + 1):
        for i in range(len(toks) - n + 1):
            grams.append(" ".join(toks[i : i + n]))
    return grams


def field_values(field: str, raw: str | None) -> list[str]:
    return [raw or "unknown"]


def emit_indices(vocab: dict[tuple[str, str], int], field: str, raw: str | None) -> list[int]:
    indices = []
    seen = set()
    for value in field_values(field, raw):
        idx = vocab.get((field, value))
        if idx is None:
            idx = vocab.get((field, "unknown"))
        if idx is not None and idx not in seen:
            indices.append(idx)
            seen.add(idx)
    return indices


def package_grams(row: dict[str, str]) -> float | None:
    try:
        grams = float(row.get("package_grams") or "")
    except ValueError:
        return None
    return grams if grams > 0 else None


class FeatureEncoder:
    def transform(self, rows: list[dict[str, str]]) -> sparse.csr_matrix:
        assert self.idf is not None
        n_struct = len(self.structured_vocab)
        n_text = len(self.text_vocab)
        package_offset = n_struct + n_text
        has_package_features = hasattr(self, "package_log_mean")
        indptr = [0]
        indices = []
        data = []
        for row in rows:
            for field in STRUCTURED_FIELDS:
                for idx in emit_indices(self.structured_vocab, field, row.get(field)):
                    indices.append(idx)
                    data.append(1.0)

            counts = Counter(ngrams(" ".join(row.get(field, "") for field in TEXT_FIELDS)))
            text_items = []
            norm = 0.0
            for term, count in counts.items():
                idx = self.text_vocab.get(term)
                if idx is None:
                    continue
                value = (1.0 + math.log(count)) * float(self.idf[idx])
                text_items.append((n_struct + idx, value))
                norm += value * value
            norm = math.sqrt(norm) or 1.0
            for idx, value in text_items:
                indices.append(idx)
                data.append(value / norm)

            if has_package_features:
                grams = package_grams(row)
                if grams is None:
                    indices.append(package_offset + 1)
                    data.append(1.0)
                else:
                    log_z = (math.log(grams) - self.package_log_mean) / self.package_log_std
                    indices.append(package_offset)
                    data.append(log_z)
                    if grams <= 20:
                        indices.append(package_offset + 2)
                        data.append(1.0)
                    if grams <= 50:
                        indices.append(package_offset + 3)
                        data.append(1.0)
                    if grams <= 100:
                        indices.append(package_offset + 4)
                        data.append(1.0)
            indptr.append(len(indices))
        width = len(getattr(self, "feature_names", [])) or len(self.structured_vocab) + len(self.text_vocab)
        return sparse.csr_matrix((data, indices, indptr), shape=(len(rows), width))


class EmbeddingFeatureEncoder:
    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(resolve_embedding_model_path(self.model_name))
        return self._model

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        keys = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
        missing_idx = [i for i, key in enumerate(keys) if key not in self._cache]
        if missing_idx:
            model = self._load_model()
            batch = [texts[i] for i in missing_idx]
            vecs = model.encode(
                batch,
                batch_size=EMBED_BATCH,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            for j, i in enumerate(missing_idx):
                self._cache[keys[i]] = vecs[j].astype(np.float32)
        return np.stack([self._cache[key] for key in keys])

    def transform(self, rows: list[dict[str, str]]) -> np.ndarray:
        n = len(rows)
        n_struct = len(self.structured_vocab)
        n_emb = self.embed_dim * len(self.text_fields)
        out = np.zeros((n, n_struct + n_emb), dtype=np.float32)
        for i, row in enumerate(rows):
            for field in STRUCTURED_FIELDS:
                for idx in emit_indices(self.structured_vocab, field, row.get(field)):
                    out[i, idx] = 1.0
        for fi, field in enumerate(self.text_fields):
            texts = [(row.get(field) or " ") for row in rows]
            vecs = self._embed_texts(texts)
            start = n_struct + fi * self.embed_dim
            out[:, start : start + self.embed_dim] = vecs
        return out


class HybridEncoder:
    def transform(self, rows: list[dict[str, str]]) -> sparse.csr_matrix:
        x_tfidf = self.tfidf.transform(rows)
        x_embed_dense = self.embed.transform(rows)
        n_struct = len(self.embed.structured_vocab)
        embed_only = x_embed_dense[:, n_struct:]
        return sparse.hstack([x_tfidf, sparse.csr_matrix(embed_only.astype(np.float64))], format="csr")


class LinearModel:
    def __init__(self, weights: np.ndarray, intercept: float):
        self.weights = weights
        self.intercept = intercept

    def predict(self, x) -> np.ndarray:
        return np.asarray(x @ self.weights + self.intercept).reshape(-1)


def install_pickle_compatibility_aliases() -> None:
    main = sys.modules["__main__"]
    main.FeatureEncoder = FeatureEncoder
    main.EmbeddingFeatureEncoder = EmbeddingFeatureEncoder
    main.HybridEncoder = HybridEncoder
    main.LinearModel = LinearModel


class ModelService:
    def __init__(
        self,
        *,
        rating_model_path: Path = RATING_MODEL_PATH,
        price_model_path: Path = PRICE_MODEL_PATH,
    ) -> None:
        install_pickle_compatibility_aliases()
        self.rating_artifact = load_pickle(rating_model_path)
        self.price_artifact = load_pickle(price_model_path)

    def predict(self, model_input: ModelInput, listed_price: ExtractedPrice) -> PredictionResult:
        row = model_input_row(model_input)
        rating = self._predict_rating(row)
        price_100g = self._predict_price(row)
        predicted_bag_price = None
        if price_100g is not None and model_input.package_grams is not None:
            predicted_bag_price = price_100g * model_input.package_grams / 100.0
        return PredictionResult(
            rating=RatingPrediction(
                predicted=round(rating, 1),
                interval_low=round(rating - 1.6, 1),
                interval_high=round(rating + 1.6, 1),
                model_version="rating/model.pkl",
            ),
            price=PricePrediction(
                predicted_price_100g_usd=round(price_100g, 2) if price_100g is not None else None,
                predicted_bag_price_usd=round(predicted_bag_price, 2) if predicted_bag_price is not None else None,
                interval_low=round(price_100g * 0.6, 2) if price_100g is not None else None,
                interval_high=round(price_100g * 1.6, 2) if price_100g is not None else None,
                model_version="price/model.pkl",
            ),
            value=value_prediction(listed_price.price_100g_usd, price_100g),
        )

    def _predict_rating(self, row: dict[str, str]) -> float:
        encoder = self.rating_artifact["encoder"]
        x = encoder.transform([row])
        model = self.rating_artifact.get("model")
        if model is not None and hasattr(model, "predict"):
            return float(model.predict(x)[0])
        return float(np.asarray(x @ self.rating_artifact["weights"] + self.rating_artifact["intercept"]).reshape(-1)[0])

    def _predict_price(self, row: dict[str, str]) -> float | None:
        encoder = self.price_artifact["encoder"]
        x = encoder.transform([row])
        weights = self.price_artifact.get("weights")
        intercept = self.price_artifact.get("intercept")
        if weights is None or intercept is None:
            return None
        pred_log = float(np.asarray(x @ weights + intercept).reshape(-1)[0])
        return max(0.0, math.exp(pred_log))


def load_pickle(path: Path):
    with path.open("rb") as f:
        return pickle.load(f)


def resolve_embedding_model_path(model_name: str) -> str:
    local_path = LOCAL_EMBEDDING_MODELS.get(model_name)
    if local_path and local_path.exists():
        return str(local_path)
    return model_name


def model_input_row(model_input: ModelInput) -> dict[str, str]:
    data = model_input.model_dump()
    return {key: "" if value is None else str(value) for key, value in data.items()}


def value_prediction(listed_price_100g: float | None, predicted_price_100g: float | None) -> ValuePrediction:
    if listed_price_100g is None or predicted_price_100g is None or predicted_price_100g <= 0:
        return ValuePrediction(verdict="insufficient_information", listed_vs_predicted_delta_pct=None)
    delta_pct = (listed_price_100g - predicted_price_100g) / predicted_price_100g * 100.0
    if delta_pct <= -20:
        verdict = "good_value"
    elif delta_pct <= 20:
        verdict = "priced_about_right"
    else:
        verdict = "expensive_for_predicted_quality"
    return ValuePrediction(verdict=verdict, listed_vs_predicted_delta_pct=round(delta_pct, 1))
