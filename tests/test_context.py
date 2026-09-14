"""Context semantics, partial answers and saved-run integrity."""

import csv
import io
from pathlib import Path

import pytest

from uk_labour_market_navigator import context, context_source, economic
from uk_labour_market_navigator import workflow as w
from uk_labour_market_navigator.market import resolve_market
from uk_labour_market_navigator.synthesis import discussion_points


def collect(places=("Sheffield",)):
    base = resolve_market(list(places), "7219")
    return context.collect(context.resolve_scope(base), base)


def test_original_populations_and_methods():
    c = collect()
    facts = {f["id"]: f for f in c["facts"]}
    assert c["status"] == "supported" and len(facts) == 12
    assert facts["E08000019.context_claimant_rate"]["value"] == "4.4"
    assert facts["K02000001.context_claimant_rate"]["value"] == "3.9"
    assert facts["E08000019.context_claimant_change"]["value"] == "0.0"
    assert facts["K02000001.context_claimant_change"]["value"] == "0.1"
    u = facts["E08000019.context_unemployment_rate"]
    assert u["value"] == "5.2" and u["quality"]["confidence_margin_pp"] == "1.4"
    assert u["source_cells"][0]["dataset"] == "NM_127_1"
    assert facts["K02000001.context_unemployment_rate"]["source_cells"][0]["dataset"] == "NM_17_5"
    assert "16+" in u["population"] and "economically active" in u["population"]
    assert "divided by residents aged 16-64" in facts["E08000019.context_claimant_rate"]["population"]
    assert facts["E08000019.context_claimant_rate"]["source_cells"][0]["period_metadata"]["value"] == "2026-07"
    assert len(facts["E08000019.context_claimant_change"]["source_cells"]) == 4
    points = discussion_points({"scope": resolve_market(["Sheffield"], "7219"), "facts": c["facts"], "context": c})
    assert any("confidence ranges overlap" in p["qualification"] for p in points if "Unemployment" in p["comparison"])


@pytest.mark.parametrize("status", ["B", "F", "G", "Q"])
def test_flagged_observation_withholds_only_affected_indicator(monkeypatch, status):
    records, ref = context_source.snapshot()
    records["aps"][("E08000019", "2026-03", "45", "20599")]["raw"]["OBS_STATUS"] = status
    monkeypatch.setattr(context, "snapshot", lambda: (records, ref))
    c = collect()
    assert c["status"] == "partial"
    assert not any("employment_rate" == row["metric"] for row in c["rows"])
    assert any(row["metric"] == "unemployment_rate" for row in c["rows"])
    assert not any(f["id"].endswith(".context_employment_rate") for f in c["facts"])


@pytest.mark.parametrize("value", ["", "NaN", "Infinity", "-1", "101"])
def test_invalid_values_are_gaps(monkeypatch, value):
    records, ref = context_source.snapshot()
    records["claimants"][("E08000019", "2026-07", "2")]["raw"]["OBS_VALUE"] = value
    monkeypatch.setattr(context, "snapshot", lambda: (records, ref))
    c = collect()
    assert not any("claimant" in f["id"] for f in c["facts"])
    assert c["gaps"] and c["facts"]


def test_missing_previous_preserves_current(monkeypatch):
    records, ref = context_source.snapshot()
    del records["claimants"][("K02000001", "2025-07", "2")]
    monkeypatch.setattr(context, "snapshot", lambda: (records, ref))
    c = collect()
    assert any(f["id"].endswith("context_claimant_rate") for f in c["facts"])
    assert not any(f["id"].endswith("context_claimant_change") for f in c["facts"])
    assert c["gaps"]


@pytest.mark.parametrize("kind", ["margin", "benchmark", "confidential"])
def test_quality_missing_benchmark_and_confidence_are_not_substituted(monkeypatch, kind):
    records, ref = context_source.snapshot()
    if kind == "margin":
        del records["aps"][("E08000019", "2026-03", "45", "21003")]
    elif kind == "benchmark":
        del records["aps"][("K02000001", "2026-03", "45", "20599")]
    else:
        records["aps"][("E08000019", "2026-03", "45", "20599")]["raw"]["OBS_CONF"] = "C"
    monkeypatch.setattr(context, "snapshot", lambda: (records, ref))
    c = collect()
    assert not any(f["id"].endswith(".context_employment_rate") for f in c["facts"])
    assert c["gaps"]


def test_mixed_nations_keep_full_claimant_comparison():
    c = collect(("Sheffield", "Belfast"))
    assert c["status"] == "partial"
    assert all("claimant" in f["id"] for f in c["facts"])
    assert all(len(row["observations"]) == 2 for row in c["rows"])
    assert any("Belfast" in gap for gap in c["gaps"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("DATE_NAME", "April 2026"),
        ("GEOGRAPHY_TYPE", "current districts"),
        ("VARIABLE_NAME", "Employment aged 16+"),
        ("RECORD_COUNT", "1"),
    ],
)
def test_source_dimensions_cannot_drift(field, value):
    import zipfile

    with zipfile.ZipFile(context_source.RESOURCES / "context-sources.zip") as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read("aps.csv").decode("utf-8-sig"))))
    rows[0][field] = value
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    with pytest.raises(ValueError):
        context_source.extract(output.getvalue().encode(), "aps")


def ready(tmp_path, included=True):
    result = w.start(
        "Fictional customer service pay discussion",
        "Explore the case",
        ["Sheffield"],
        "7219",
        [],
        tmp_path,
        release=True,
        include_pay=True,
        include_demand=True,
        include_context=included,
    )
    run = Path(result["run"])
    assert w.gather(run, True, True)["status"] == "awaiting_synthesis"
    e = w.read(run / "evidence.json")
    draft = {
        "title": "A pay discussion",
        "opening": "Public evidence informs the discussion.",
        "sections": [
            {
                "heading": "Consider the context",
                "text": "The evidence is descriptive and does not identify an appropriate increase.",
                "fact_ids": [f["id"] for f in e["facts"]],
            }
        ],
        "next_questions": ["Discuss the offer and candidate feedback."],
        "reviewed_by_host": True,
    }
    assert w.publish(run, draft)["status"] == "ready"
    return run, e


@pytest.mark.parametrize("target", ["evidence.json", "brief.html", "plan.json"])
def test_context_tamper_with_repaired_hash_still_withdraws(tmp_path, target):
    run, e = ready(tmp_path)
    path = run / target
    if target == "evidence.json":
        e["context"]["facts"][0]["value"] = "0.1"
        w.write(path, e)
    elif target == "plan.json":
        p = w.read(path)
        p["economic_scope"]["prices"] = "Sheffield prices"
        w.write(path, p)
    else:
        w.write_text(path, path.read_text(encoding="utf-8").replace("4.4%", "0.1%", 1))
    seal = w.read(run / "evidence-seal.json")
    if target in seal:
        seal[target] = w.digest(path)
        w.write(run / "evidence-seal.json", seal)
    manifest = w.read(run / "manifest.json")
    manifest["hashes"][target] = w.digest(path)
    w.write(run / "manifest.json", manifest)
    assert w.verify(run)["status"] == "withdrawn"


def test_historical_format_thirteen_remains_unchanged(tmp_path):
    from uk_labour_market_navigator._report_v13 import render

    run, e = ready(tmp_path, False)
    for name, text in render(w.read(run / "plan.json"), e, w.read(run / "synthesis.json")).items():
        w.write_text(run / name, text)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 13
    manifest["hashes"] = {n: w.digest(run / n) for n in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    assert w.verify(run)["status"] == "ready"
    assert before == {p.name: p.read_bytes() for p in run.iterdir()}
    assert "context" not in e and "economic" not in e


@pytest.mark.parametrize("family", ["context", "economic"])
def test_source_failure_preserves_independent_families(tmp_path, monkeypatch, family):
    def fail():
        raise ValueError("corrupted source")

    monkeypatch.setattr(context if family == "context" else economic, "snapshot", fail)
    run, e = ready(tmp_path)
    assert e[family]["status"] == "evidence_gap" and not e[family]["facts"]
    assert e["pay"]["facts"] and e["census"]["facts"]
    assert e["economic" if family == "context" else "context"]["facts"]
    assert w.verify(run)["status"] == "ready"


def test_economic_definitions_windows_and_no_uplift():
    c = economic.collect(economic.resolve_scope())
    assert [f["value"] for f in c["facts"]] == ["3.1", "2.9", "3.5", "4.1"]
    assert [r["geography"] for r in c["rows"]] == ["United Kingdom"] * 2 + ["Great Britain"] * 2
    assert c["rows"][0]["period"] != c["rows"][2]["period"]
    assert "Excludes bonuses" in c["rows"][2]["basis"]
    assert "Includes bonuses" in c["rows"][3]["basis"]
    assert all(f["unit"] == "percent_year_on_year" for f in c["facts"])
    assert all("salary uplift" in f["calculation"] for f in c["facts"])


def test_economic_missing_or_relabelled_source_cannot_publish():
    import zipfile

    with zipfile.ZipFile(economic.RESOURCES / "economic-sources.zip") as archive:
        body = archive.read("kai9.csv")
    for changed in [
        body.replace(b'"2026 JUN","3.5"', b'"2026 JUN",""'),
        body.replace(b'"Unit","%"', b'"Unit","GBP"'),
        body.replace(b'"2026 JUN","3.5"', b'"2026 MAY","3.5"'),
    ]:
        with pytest.raises(ValueError):
            economic.extract(changed, "kai9")


@pytest.mark.parametrize("module,prefix", [(context_source, "context"), (economic, "economic")])
def test_installed_archive_and_reference_hashes_are_required(tmp_path, monkeypatch, module, prefix):
    original = module.RESOURCES
    for suffix in ("reference.json", "sources.zip"):
        (tmp_path / (prefix + "-" + suffix)).write_bytes((original / (prefix + "-" + suffix)).read_bytes())
    monkeypatch.setattr(module, "RESOURCES", tmp_path)
    path = tmp_path / (prefix + "-sources.zip")
    good = path.read_bytes()
    path.write_bytes(good + b"tamper")
    with pytest.raises(ValueError):
        module.snapshot()
    path.write_bytes(good)
    path = tmp_path / (prefix + "-reference.json")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        module.snapshot()


@pytest.mark.parametrize("omit", [False, True])
def test_cli_discloses_context_before_acceptance(tmp_path, capsys, omit):
    import json

    from uk_labour_market_navigator.__main__ import main

    args = [
        "start",
        "Fictional hiring discussion",
        "--place",
        "Sheffield",
        "--role",
        "7219",
        "--runs-dir",
        str(tmp_path),
    ]
    if omit:
        args.append("--no-context")
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    plan = w.read(Path(result["run"]) / "plan.json")
    assert plan["scope_accepted"] is False
    assert bool(plan.get("economic_scope")) is not omit
    assert ("Great Britain average earnings" in result["proposal"]) is not omit
    assert not (Path(result["run"]) / "evidence.json").exists()
    assert w.gather(Path(result["run"]), False, True)["status"] == "scope_choice"
    assert not (Path(result["run"]) / "evidence.json").exists()


def test_context_report_has_clean_unicode_and_both_formats(tmp_path):
    run, _ = ready(tmp_path)
    for name in ("brief.html", "brief.md"):
        text = (run / name).read_text(encoding="utf-8")
        assert "\u00c2" not in text and "\ufffd" not in text
        assert "71.6% \u00b13.3 pp" in text
        assert "Prices and earnings growth" in text
        assert "not a change over time" in text
