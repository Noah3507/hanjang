from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path

from PIL import Image
from pydantic import ValidationError
import pytest

from contract_models import CandidateSet, Ranking, RankOutput, validate_batch_order, validate_linkage

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load(name):
    return json.loads((FIXTURES / "contracts" / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["ranking.mock.json", "ranking.model.json", "ranking.fallback.json"])
def test_ranking_examples(name):
    candidates = CandidateSet.model_validate(load("candidates.json"))
    ranking = Ranking.model_validate(load(name))
    validate_linkage(candidates, ranking)


def test_candidate_examples_and_ad_image_contract():
    candidates = CandidateSet.model_validate(load("candidates.json"))
    for candidate in candidates.candidates:
        with Image.open(FIXTURES / "ads" / f"{candidate.strategy}.png") as image:
            image.load()
            assert image.format == "PNG" and image.size == (1080, 1350)
            assert image.mode == "RGB" and "transparency" not in image.info


@pytest.mark.parametrize("name,model", [("candidates.schema.json", CandidateSet), ("ranking.schema.json", Ranking)])
def test_exported_schema_matches_executable_spec(name, model):
    assert load(name) == model.model_json_schema()


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), -float("inf"), True])
def test_rejects_nonfinite_or_boolean_score(bad_score):
    body = load("ranking.mock.json")
    body["items"][0]["score"] = bad_score
    with pytest.raises(ValidationError):
        Ranking.model_validate(body)


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra", "rank", "order", "unknown", "feature"])
def test_rejects_invalid_ranking(change):
    body = load("ranking.mock.json")
    if change == "missing": body["items"].pop()
    elif change == "extra": body["items"].append(deepcopy(body["items"][0]))
    elif change == "duplicate": body["items"][1]["candidate_id"] = body["items"][0]["candidate_id"]
    elif change == "rank": body["items"][1]["rank"] = 1
    elif change == "order": body["items"].reverse()
    elif change == "unknown": body["ctr_prediction"] = 0.8
    else: body["feature_version"] = "invented-feature"
    with pytest.raises(ValidationError):
        Ranking.model_validate(body)


@pytest.mark.parametrize("change", ["range", "nan", "self", "reversed", "duplicate", "missing", "method", "formula", "mock"])
def test_pairwise_semantics(change):
    body = load("ranking.model.json")
    pairs = body["pairwise"]["comparisons"]
    if change == "range": pairs[0]["probability_a_preferred"] = 1.1
    elif change == "nan": pairs[0]["probability_a_preferred"] = float("nan")
    elif change == "self": pairs[0]["candidate_b_id"] = pairs[0]["candidate_a_id"]
    elif change == "reversed": pairs[0]["candidate_a_id"], pairs[0]["candidate_b_id"] = pairs[0]["candidate_b_id"], pairs[0]["candidate_a_id"]
    elif change == "duplicate": pairs[1] = deepcopy(pairs[0])
    elif change == "missing": pairs.pop()
    elif change == "method": body["pairwise"]["method"] = "purchase_probability"
    elif change == "formula": pairs[0]["probability_a_preferred"] = 0.5
    else: body["source"] = "mock"; body["feature_version"] = None; body["model_version"] = "mock-v1"
    with pytest.raises(ValidationError):
        Ranking.model_validate(body)


@pytest.mark.parametrize("change", ["facts", "text", "strategy", "id", "revision", "size"])
def test_rejects_candidate_drift(change):
    body = load("candidates.json")
    candidate = body["candidates"][0]
    if change == "facts": candidate["facts"]["price_text"] = "changed"
    elif change == "text": candidate["renderer"]["text_boxes"][0]["text"] = "trimmed"
    elif change == "strategy": candidate["strategy"] = body["candidates"][1]["strategy"]
    elif change == "id": candidate["candidate_id"] = body["candidates"][1]["candidate_id"]
    elif change == "revision": candidate["png"]["revision"] = 2
    else: candidate["png"]["width"] = 512
    with pytest.raises(ValidationError):
        CandidateSet.model_validate(body)


def test_ties_are_deterministic_and_probabilities_optional():
    body = load("ranking.model.json")
    body.pop("pairwise")
    for rank, item in enumerate(sorted(body["items"], key=lambda item: item["candidate_id"]), 1):
        item["score"] = -1.0
        item["rank"] = rank
    body["items"].sort(key=lambda item: item["rank"])
    assert Ranking.model_validate(body).pairwise is None


def test_pairwise_complement_and_input_order_is_not_display_order():
    body = load("ranking.model.json")
    ranking = Ranking.model_validate(body)
    ids = sorted(item.candidate_id for item in ranking.items)
    assert len(list(combinations(ids, 2))) == 6
    assert [item["candidate_id"] for item in load("candidates.json")["candidates"]] != [item.candidate_id for item in ranking.items]
    for pair in ranking.pairwise.comparisons:
        reverse_probability = 1 - pair.probability_a_preferred
        assert 0 <= reverse_probability <= 1


def test_batch_output_preserves_ids_and_rejects_sorting_by_rank():
    ids = [item["candidate_id"] for item in load("candidates.json")["candidates"]]
    output = RankOutput.model_validate(load("rank-output.model.json"))
    validate_batch_order(ids, output)
    output.items.sort(key=lambda item: item.rank)
    with pytest.raises(ValueError):
        validate_batch_order(ids, output)


@pytest.mark.parametrize("change", ["id", "revision"])
def test_cross_response_id_and_revision_mismatch(change):
    candidates = CandidateSet.model_validate(load("candidates.json"))
    body = load("ranking.mock.json")
    if change == "id": body["items"][0]["candidate_id"] = "unexpected"
    else: body["revision"] = 2
    ranking = Ranking.model_validate(body)
    with pytest.raises(ValueError):
        validate_linkage(candidates, ranking)


def test_batch_schema_export():
    assert load("rank-output.schema.json") == RankOutput.model_json_schema()
