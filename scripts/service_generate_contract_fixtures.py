"""Regenerate synthetic, non-user contract fixtures; no model/network access."""
from hashlib import sha256
from io import BytesIO
from itertools import combinations
import json
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/integration"))
from contract_models import CandidateSet, Ranking, RankOutput  # noqa: E402


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    ads = ROOT / "tests/fixtures/ads"
    contracts = ROOT / "tests/fixtures/contracts"
    ads.mkdir(parents=True, exist_ok=True)
    contracts.mkdir(parents=True, exist_ok=True)
    product = Image.new("RGB", (600, 600), "#d39142")
    source = BytesIO()
    product.save(source, "PNG")
    checksum = sha256(source.getvalue()).hexdigest()
    facts = dict(store_name="  Fixture Shop  ", product_name="Sample Product", price_text=" 10,500 KRW ", address=None, instagram_handle=None)
    candidates = []
    strategies = ["emotional", "price", "visual", "brand"]  # Stable input order, not rank order.
    for i, strategy in enumerate(strategies):
        image = Image.new("RGB", (1080, 1350), ["#fff4e0", "#ffe5cc", "#e0f0ff", "#e8e0f0"][i])
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=42)
        draw.rectangle((150, 300, 930, 950), fill="#d39142")
        draw.text((60, 60), f"SYNTHETIC {strategy.upper()} FIXTURE", font=ImageFont.load_default(size=32), fill="#181818")
        text_boxes = []
        for field, y in [("store_name", 1050), ("product_name", 1120), ("price_text", 1190)]:
            draw.text((60, y), facts[field], font=font, fill="#181818")
            text_boxes.append(dict(field=field, text=facts[field], x=60.0, y=float(y), width=960.0, height=60.0,
                                   font_size_px=42.0, font_weight=400, foreground="#181818", background=None, overflow=False))
        image.save(ads / f"{strategy}.png", "PNG")
        candidates.append(dict(candidate_id=f"c_{strategy}", strategy=strategy, revision=1, facts=facts,
            copy=dict(headline=f"Synthetic {strategy} fixture", body="", cta=""),
            png=dict(asset_id=f"fixture_{strategy}", url=f"/api/v1/assets/fixture_{strategy}", mime_type="image/png", width=1080, height=1350, revision=1),
            renderer=dict(template_version="contract-fixture-v1", canvas_width=1080, canvas_height=1350,
                          text_boxes=text_boxes, product_bbox=dict(x=150.0, y=300.0, width=780.0, height=650.0),
                          photo_sha256=checksum, processed_photo_sha256=checksum),
            diagnostics=dict(status="unavailable", rules_version="fixture-only", min_font_size_px=None,
                             min_contrast_ratio=None, text_overlap_ratio=None, product_overlap_ratio=None,
                             layout_order=None, attention=None, warnings=[])))
    candidate_set = dict(candidates=candidates)
    CandidateSet.model_validate(candidate_set)
    write_json(contracts / "candidates.json", candidate_set)
    scores = dict(c_visual=0.8, c_emotional=0.6, c_price=0.4, c_brand=0.2)
    items = [dict(candidate_id=key, score=value, rank=rank) for rank, (key, value) in enumerate(sorted(scores.items(), key=lambda item: (-item[1], item[0])), 1)]
    mock = dict(source="mock", model_version="mock-v1", feature_version=None, revision=1, items=items, pairwise=None)
    model = dict(source="model", model_version="synthetic-example-v1", feature_version="synthetic-features-v1", revision=1, items=items,
                 pairwise=dict(method="bradley_terry_sigmoid_v1", comparisons=[dict(candidate_a_id=a, candidate_b_id=b,
                    probability_a_preferred=1 / (1 + math.exp(-(scores[a] - scores[b])))) for a, b in combinations(sorted(scores), 2)]))
    fallback = dict(mock, source="fallback_mock")
    for name, value in [("ranking.mock.json", mock), ("ranking.model.json", model), ("ranking.fallback.json", fallback)]:
        Ranking.model_validate(value)
        write_json(contracts / name, value)
    write_json(contracts / "candidates.schema.json", CandidateSet.model_json_schema())
    write_json(contracts / "ranking.schema.json", Ranking.model_json_schema())
    by_id = {item["candidate_id"]: item for item in items}
    output = dict(model_version=model["model_version"], feature_version=model["feature_version"],
                  items=[by_id[candidate["candidate_id"]] for candidate in candidates], pairwise=model["pairwise"])
    RankOutput.model_validate(output)
    write_json(contracts / "rank-output.model.json", output)
    write_json(contracts / "rank-output.schema.json", RankOutput.model_json_schema())
    print("Generated four synthetic RGB ads, contract examples and schemas; no network/model used")


if __name__ == "__main__":
    main()
