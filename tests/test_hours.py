import copy
from pathlib import Path
from unittest.mock import patch

import pytest

from uk_labour_market_navigator import hours
from uk_labour_market_navigator import workflow as w
from uk_labour_market_navigator.identities import reference


def scope(pattern="full_time"):
    return hours.option(reference()["occupations"]["7219"], pattern)


def start(tmp_path, **options):
    args = dict(release=True, include_pay=True, include_hours=True, include_context=True)
    args.update(options)
    result = w.start(
        "Fictional pay and hours discussion", "Assess the offer", ["Sheffield"], "7219", [], tmp_path, **args
    )
    return Path(result["run"]), result


def finish(run):
    e = w.read(run / "evidence.json")
    draft = {
        "title": "Pay and the working week",
        "opening": "Separate benchmarks inform the offer discussion.",
        "sections": [
            {
                "heading": "Compare the whole offer",
                "text": "Paid hours provide context, not a working week associated with median annual pay.",
                "fact_ids": [f["id"] for f in e["facts"]],
            }
        ],
        "next_questions": ["Discuss duties, paid hours and the full offer."],
        "reviewed_by_host": True,
    }
    assert w.publish(run, draft)["status"] == "ready"
    return e


def test_original_hours_mean_median_and_overtime_populations():
    e = hours.collect(scope())
    assert [f["value"] for f in e["facts"]] == ["37.3", "37.2", "37.4", "37.8", "2.3", "0.6"]
    assert "Excludes zero" in e["facts"][-2]["population"]
    assert "Includes zero" in e["facts"][-1]["population"]
    assert all(f["unit"] == "hours/week" and len(f["source_cells"]) == 2 for f in e["facts"])
    assert all("April 2025" in f["period"] for f in e["facts"])
    assert "full-time" in e["facts"][0]["population"]
    assert hours.collect(scope("part_time"))["facts"][0]["value"] != "37.3"


@pytest.mark.parametrize("raw,cv", [("x", "0.2"), ("37.3", "x"), ("37.3", "20.1"), ("-", "0.2")])
def test_hours_suppression_missing_and_precision_withhold_only_affected_cell(raw, cv):
    records = copy.deepcopy(hours.snapshot())
    pair = records["7219/full_time/basic"]["values"]["median"]
    pair.update(raw_value=raw, raw_cv=cv)
    with patch.object(hours, "snapshot", return_value=records):
        e = hours.collect(scope())
    assert len(e["facts"]) == 5
    assert not any(f["id"] == "hours.basic_median" for f in e["facts"])
    assert e["rows"][0]["median"] == "Unavailable" and e["gaps"]


def test_hours_scope_requires_acceptance_and_declined_pay_omits_hours(tmp_path):
    run, result = start(tmp_path)
    assert "not the hours associated" in result["proposal"]
    assert not (run / "evidence.json").exists()
    assert w.gather(run, False, True)["status"] == "scope_choice"
    assert w.gather(run, True)["status"] == "scope_choice"
    assert w.gather(run, True, False)["status"] == "awaiting_synthesis"
    e = finish(run)
    assert e["hours"]["status"] == "declined" and not e["hours"]["facts"]
    assert "paid working week look" not in (run / "brief.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("context", [True, False])
def test_hours_new_plan_runs_with_or_without_context(tmp_path, context):
    run, _ = start(tmp_path, include_context=context)
    assert w.gather(run, True, True)["status"] == "awaiting_synthesis"
    e = finish(run)
    assert w.read(run / "plan.json")["schema_version"] == 5
    assert w.read(run / "manifest.json")["version"] == 15
    assert bool(e.get("context")) == context
    assert len(e["hours"]["facts"]) == 6
    for filename in ("brief.html", "brief.md"):
        text = (run / filename).read_text(encoding="utf-8")
        assert "not necessarily the hours worked" in text
        assert "averages include jobs with no paid overtime" in text
        assert "37.2" in text and "37.8" in text
        assert "\u00c2" not in text and "\ufffd" not in text
    assert w.verify(run)["status"] == "ready"


def test_hours_source_failure_keeps_earnings(tmp_path):
    with patch.object(hours, "snapshot", side_effect=ValueError("source changed")):
        run, _ = start(tmp_path)
        assert w.gather(run, True, True)["status"] == "awaiting_synthesis"
        e = finish(run)
        assert e["hours"]["status"] == "evidence_gap" and not e["hours"]["facts"]
        assert e["pay"]["facts"] and e["context"]["facts"]


@pytest.mark.parametrize("target", ["evidence.json", "plan.json", "brief.html"])
def test_tamper_repaired_hashes_still_withdraw(tmp_path, target):
    run, _ = start(tmp_path)
    w.gather(run, True, True)
    finish(run)
    path = run / target
    if target == "brief.html":
        w.write_text(path, path.read_text(encoding="utf-8").replace("37.3", "39.9"))
    else:
        data = w.read(path)
        if target == "plan.json":
            data["hours_scope"]["working_pattern"] = "part_time"
        else:
            data["hours"]["facts"][0]["value"] = "39.9"
        w.write(path, data)
    for name, nested in (("evidence-seal.json", False), ("manifest.json", True)):
        seal = w.read(run / name)
        values = seal["hashes"] if nested else seal
        if target in values:
            values[target] = w.digest(path)
        w.write(run / name, seal)
    assert w.verify(run)["status"] == "withdrawn"


def test_prior_context_report_remains_byte_for_byte_verifiable(tmp_path):
    from uk_labour_market_navigator._report_v14 import render

    run, _ = start(tmp_path, include_hours=False)
    w.gather(run, True, True)
    e = finish(run)
    for name, text in render(w.read(run / "plan.json"), e, w.read(run / "synthesis.json")).items():
        w.write_text(run / name, text)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 14
    manifest["hashes"] = {name: w.digest(run / name) for name in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    assert w.verify(run)["status"] == "ready"
    assert before == {p.name: p.read_bytes() for p in run.iterdir()}


def test_pack_pin_cannot_be_self_approved(tmp_path, monkeypatch):
    p = tmp_path / "hours.json.gz"
    p.write_bytes((hours.RESOURCES / p.name).read_bytes() + b"tamper")
    monkeypatch.setattr(hours, "RESOURCES", tmp_path)
    with pytest.raises(ValueError):
        hours.snapshot()


def test_example_first_pass_keeps_notes_collapsible_and_links_intact():
    from html.parser import HTMLParser

    class Reader(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids, self.links, self.depth, self.visible = [], [], 0, []
            self.in_summary = False

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if "id" in attrs:
                self.ids.append(attrs["id"])
            if tag == "a" and attrs.get("href", "").startswith("#"):
                self.links.append(attrs["href"][1:])
            if tag == "details":
                self.depth += 1
            if tag == "summary":
                self.in_summary = True

        def handle_endtag(self, tag):
            if tag == "details":
                self.depth -= 1
            if tag == "summary":
                self.in_summary = False

        def handle_data(self, data):
            if not self.depth:
                self.visible.append(data)

    text = (Path(__file__).parents[1] / "examples/brief.html").read_text(encoding="utf-8")
    parser = Reader()
    parser.feed(text)
    assert len(parser.ids) == len(set(parser.ids))
    assert set(parser.links) <= set(parser.ids)
    assert parser.depth == 0
    assert text.count('<article class="insight">') == 4
    visible = " ".join(parser.visible)
    assert "not necessarily the hours worked" in visible
    assert "averages include jobs with no paid overtime" in visible
    assert "Technical source record" not in visible
    assert 'class="steps"' in text and '<th scope="col">Mean (average)</th>' in text
