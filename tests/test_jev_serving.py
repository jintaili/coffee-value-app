import pickle

import pytest

from coffee_value.extraction.questions import QUESTIONS
from coffee_value_app.jev_extractor import JevExtractor
from coffee_value_app.jev_extractor import _name_and_roaster, _summary_process
from coffee_value_app.model_runtime import JEV_PRICE_MODEL_PATH, JevPriceModel, ModelArtifactContractError
from coffee_value_app.schemas import ModelInput
from coffee_value_app.model_runtime import model_input_row


def answer(question, choice):
    options = question["criteria"]
    return {"type": "choice", "choice": choice,
            "probabilities": {option: float(option == choice) for option in options}}


def base_answers():
    return {key: answer(question, "not_stated" if "not_stated" in question["criteria"]
                        else next(iter(question["criteria"]))) for key, question in QUESTIONS.items()}


def test_portable_price_matches_saved_training_prediction():
    """Golden value calculated from the original training bundle's predict method."""
    answers = base_answers()
    answers["origin_country"] = answer(QUESTIONS["origin_country"], "Panama")
    answers["variety_gesha"] = answer(QUESTIONS["variety_gesha"], "supported")
    from coffee_value.extraction.questions import CONTRACT_VERSION, MODEL, question_hash
    record = {"status": "complete", "contract_version": CONTRACT_VERSION,
              "question_hash": question_hash(), "requested_model": MODEL,
              "resolved_model": MODEL, "answers": answers}
    row = model_input_row(ModelInput(
        origin_country="Panama", process_method="washed", variety="gesha",
        is_blend="false", is_espresso="false", is_decaf="false",
        producer_or_farm_present="true", altitude_present="true", roaster_country="US",
        sensory_text="jasmine mango floral", producer_text="small farm in Boquete Panama",
        package_grams=226.8))
    assert JevPriceModel().predict(row, record) == pytest.approx(19.2857312048876, abs=1e-10)


def test_jev_price_rejects_changed_feature_contract(tmp_path):
    with JEV_PRICE_MODEL_PATH.open("rb") as stream:
        artifact = pickle.load(stream)
    artifact["feature_names"][-6] = "tfidf:unrelated"
    path = tmp_path / "changed.pkl"
    path.write_bytes(pickle.dumps(artifact))
    with pytest.raises(ModelArtifactContractError, match="out of order"):
        JevPriceModel(path)


def test_product_summary_process_remains_visible_when_prose_conflicts():
    text = ("Description: This natural lot has a long history.\n"
            "Coffee Summary\nABSTRACT\nKenya\nORIGIN\nDry Washed\nPROCESS METHOD\n")
    assert _summary_process(text) == "Dry Washed"
    name, roaster = _name_and_roaster(
        "<title>Kenya Kamunyaka AA\n– Onyx Coffee Lab</title><h1>K e n y a</h1>",
        "https://onyxcoffeelab.com/products/kenya-kamunyaka-aa")
    assert name == "Kenya Kamunyaka AA"
    assert roaster == "Onyx Coffee Lab"


@pytest.mark.anyio
async def test_jev_extracts_product_and_copies_commerce_values():
    html = '''<html><head><title>Panama Gesha | Example Roaster</title>
    <meta property="og:site_name" content="Example Roaster">
    <script type="application/ld+json">{"@type":"Product","name":"Panama Gesha",
    "offers":{"@type":"Offer","price":"46.00","priceCurrency":"USD"}}</script>
    </head><body><h1>Panama Gesha</h1><p>Origin: Panama</p>
    <p>Process: Washed</p><p>Variety: Gesha</p><p>Tasting Notes: Jasmine, mango</p>
    <p>8 oz</p></body></html>'''

    def fake_evaluate(state, *, questions, model, timeout, attempts):
        answers = base_answers()
        answers["origin_country"] = answer(questions["origin_country"], "Panama")
        answers["process_washed"] = answer(questions["process_washed"], "supported")
        answers["variety_gesha"] = answer(questions["variety_gesha"], "supported")
        for key in questions.keys() - answers.keys():
            selected = {"page_type": "coffee_product", "price_type": "one_time",
                        "availability": "in_stock"}.get(key, "none")
            answers[key] = answer(questions[key], selected)
        return {"model": model, "answers": answers}, 0.1, 1

    result = await JevExtractor(evaluate_fn=fake_evaluate).extract(
        url="https://example.com/products/panama-gesha", page_text="Origin: Panama\nProcess: Washed\nVariety: Gesha\nTasting Notes: Jasmine, mango\n8 oz\n$46",
        html=html)
    assert result.page.page_type == "coffee_product"
    assert result.page.coffee.origin_country == "Panama"
    assert result.page.coffee.process_method == ["washed"]
    assert result.page.coffee.display_tasting_notes == "Jasmine, mango"
    assert result.page.price.listed_price == 46
    assert set(result.record["answers"]) == set(QUESTIONS)
