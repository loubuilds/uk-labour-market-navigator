"""Acceptance failures: draft ingestion, useful comparisons and saved-run continuity."""

import json
from pathlib import Path

import pytest

from uk_labour_market_navigator import workflow as w
from uk_labour_market_navigator.evidence import ScopeChoice
from uk_labour_market_navigator.market import resolve_market
from uk_labour_market_navigator.synthesis import discussion_points


def prepare(tmp_path, places=None, role="2134"):
    result = w.start(
        "Explore this occupation",
        "Prepare a discussion",
        places or ["Reading"],
        role,
        [],
        tmp_path,
        release=True,
        include_demand=True,
        include_pay=True,
    )
    run = Path(result["run"])
    assert w.gather(run, True, True)["status"] == "awaiting_synthesis"
    evidence = w.read(run / "evidence.json")
    draft = {
        "title": "A starting view",
        "opening": "Occupation context for the discussion.",
        "sections": [
            {
                "heading": "The evidence",
                "text": "These are distinct dated views of the occupation.",
                "fact_ids": [evidence["facts"][0]["id"]],
            }
        ],
        "next_questions": ["Would a comparison with another district help?"],
        "reviewed_by_host": True,
    }
    return run, evidence, draft


def test_bom_draft_is_accepted_but_saved_evidence_stays_strict(tmp_path):
    run, evidence, draft = prepare(tmp_path)
    external = tmp_path / "editor-draft.json"
    external.write_text(json.dumps(draft), encoding="utf-8-sig")
    assert w.publish(run, w.read_draft(external))["status"] == "ready"
    assert not (run / "synthesis.json").read_bytes().startswith(b"\xef\xbb\xbf")
    original = (run / "evidence.json").read_bytes()
    (run / "evidence.json").write_bytes(b"\xef\xbb\xbf" + original)
    assert w.verify(run)["status"] == "withdrawn"
    assert (run / "evidence.json").read_bytes() == b"\xef\xbb\xbf" + original


def test_draft_error_identifies_field_and_preserves_retry(tmp_path):
    run, evidence, draft = prepare(tmp_path)
    draft["sections"][0]["text"] = "Census 2021 provides context."
    with pytest.raises(ValueError, match=r"sections\[0\].text:.*dates"):
        w.publish(run, draft)
    assert w.verify(run)["status"] == "incomplete"
    draft["sections"][0]["text"] = "The Census provides historical context."
    draft["sections"][0]["fact_ids"] = []
    with pytest.raises(ValueError, match=r"sections\[0\].fact_ids"):
        w.publish(run, draft)
    draft["sections"][0]["fact_ids"] = [evidence["facts"][0]["id"]]
    assert w.publish(run, draft)["status"] == "ready"


def test_actual_comparison_directions_and_references(tmp_path):
    run, evidence, draft = prepare(tmp_path, ["Reading", "Cambridge"])
    points = w.read(run / "synthesis-context.json")["discussion_points"]
    paired = [p for p in points if "compared with" in p["comparison"]]
    assert len(paired) == 3
    assert all("Reading compared with Cambridge: lower" in p["comparison"] for p in paired)
    ids = {f["id"] for f in evidence["facts"]}
    assert all(set(p["fact_ids"]) <= ids for p in points)
    assert any("England and Wales" in p["comparison"] for p in points)
    assert w.publish(run, draft)["status"] == "ready"


def test_missing_family_never_produces_comparison_point(tmp_path):
    run, evidence, draft = prepare(tmp_path, ["Edinburgh", "Belfast"])
    points = discussion_points(evidence)
    assert len(points) == 1
    assert all(i.endswith(".new_adverts") for i in points[0]["fact_ids"])
    assert w.publish(run, draft)["answerability"] == "partial"
    html = (run / "brief.html").read_text(encoding="utf-8")
    workforce = html.split("Resident workforce", 1)[1].split("</section>", 1)[0]
    assert "unavailable" in workforce and "People aged sixteen" not in workforce


def test_equal_published_values_remain_a_tie():
    e = {
        "scope": {"places": [{"id": "a", "label": "Alpha"}, {"id": "b", "label": "Beta"}]},
        "facts": [{"id": "a.count", "value": "10"}, {"id": "b.count", "value": "10"}],
    }
    (point,) = discussion_points(e)
    assert "equal published" in point["comparison"] and "tie" in point["qualification"]


def test_suppressed_pay_explains_accepted_scope(tmp_path):
    run, evidence, draft = prepare(tmp_path, role="3312")
    assert not evidence["pay"]["facts"]
    assert w.publish(run, draft)["status"] == "ready"
    html = (run / "brief.html").read_text(encoding="utf-8")
    pay = html.split("Official earnings", 1)[1].split("</section>", 1)[0]
    for term in ("full time", "annual gross", "ASHE 2025", "not zero", "Tax year ending 5 April 2025"):
        assert term in pay


def test_prior_version_seven_report_replays_without_mutation(tmp_path):
    from uk_labour_market_navigator._report_v7 import render

    run, evidence, draft = prepare(tmp_path)
    w.publish(run, draft)
    for name, text in render(w.read(run / "plan.json"), evidence, draft).items():
        w.write_text(run / name, text)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 7
    manifest["hashes"] = {name: w.digest(run / name) for name in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    assert w.verify(run)["status"] == "ready"
    assert before == {p.name: p.read_bytes() for p in run.iterdir()}


def test_plain_police_role_still_needs_meaning():
    with pytest.raises(ScopeChoice):
        resolve_market(["Reading"], "police officers")
