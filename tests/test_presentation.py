"""Presentation changes preserve source units and older verified reports."""

from decimal import Decimal
from pathlib import Path

import pytest

from uk_labour_market_navigator import workflow as w


def ready(tmp_path, measure):
    run = Path(
        w.start(
            "Fictional customer service hiring",
            "Assess the evidence",
            ["Sheffield"],
            "7219",
            [],
            tmp_path,
            release=True,
            requested_role="customer service advisers",
            include_demand=True,
            include_pay=True,
            pay_measure=measure,
        )["run"]
    )
    w.gather(run, True, True)
    e = w.read(run / "evidence.json")
    draft = {
        "title": "Test the explanation before changing the offer",
        "opening": "A fictional discussion using public evidence.",
        "sections": [
            {
                "heading": "Earnings context",
                "text": "The national benchmark does not establish a competitive local offer.",
                "fact_ids": ["pay.median"],
            }
        ],
        "next_questions": ["Would another earnings measure help?"],
        "reviewed_by_host": True,
    }
    assert w.publish(run, draft)["status"] == "ready"
    return run, e


@pytest.mark.parametrize(
    "measure,unit,suffix,precision",
    [("annual_gross", "GBP/year", "a year", 0), ("hourly_excluding_overtime", "GBP/hour", "an hour", 2)],
)
def test_currency_presentation_preserves_units_and_tamper_detection(tmp_path, measure, unit, suffix, precision):
    run, e = ready(tmp_path, measure)
    fact = next(f for f in e["pay"]["facts"] if f["id"] == "pay.median")
    display = f"£{Decimal(fact['value']):,.{precision}f} {suffix}"
    assert fact["unit"] == unit
    for name in ("brief.html", "brief.md"):
        text = (run / name).read_text(encoding="utf-8")
        assert display in text and unit in text
        assert "\u00c2" not in text and "\ufffd" not in text
    original = (run / "evidence.json").read_bytes()
    assert w.verify(run)["status"] == "ready"
    html = run / "brief.html"
    html.write_text(html.read_text(encoding="utf-8").replace(display, "£1 a year", 1), encoding="utf-8")
    assert w.verify(run)["status"] == "withdrawn"
    assert (run / "evidence.json").read_bytes() == original


def test_format_nine_reopens_without_currency_rewrite(tmp_path):
    from uk_labour_market_navigator._report_v9 import render

    run, e = ready(tmp_path, "annual_gross")
    for name, text in render(w.read(run / "plan.json"), e, w.read(run / "synthesis.json")).items():
        w.write_text(run / name, text)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 9
    manifest["hashes"] = {n: w.digest(run / n) for n in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    assert "GBP 27,848/year" in (run / "brief.html").read_text(encoding="utf-8")
    assert w.verify(run)["status"] == "ready"
    assert before == {p.name: p.read_bytes() for p in run.iterdir()}


def test_format_ten_reopens_without_reordering_or_writing(tmp_path):
    from uk_labour_market_navigator._report_v10 import render

    run, e = ready(tmp_path, "annual_gross")
    for name, text in render(w.read(run / "plan.json"), e, w.read(run / "synthesis.json")).items():
        w.write_text(run / name, text)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 10
    manifest["hashes"] = {n: w.digest(run / n) for n in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    assert w.verify(run)["status"] == "ready"
    assert before == {p.name: p.read_bytes() for p in run.iterdir()}
    html = (run / "brief.html").read_text(encoding="utf-8")
    assert html.index("Resident workforce") < html.index("What to take into the discussion")


def test_current_opening_keeps_interpretation_labelled_and_checked(tmp_path):
    run, _ = ready(tmp_path, "annual_gross")
    assert w.read(run / "manifest.json")["version"] == 15
    for name in ("brief.html", "brief.md"):
        text = (run / name).read_text(encoding="utf-8")
        assert (
            text.index("interpretation is AI-assisted")
            < text.index("Earnings context")
            < text.index("Resident workforce")
        )
        assert text.count("interpretation is AI-assisted") == 1
        assert "n.e.c.." not in text.split("Technical source record")[0]
        assert "Source figures are checked against official data" in text
        assert text.count("The national benchmark does not establish a competitive local offer.") == 1
        assert "Census 2021" in text and "June is partly imputed" in text
    # Changing prose and repairing its file hash still fails regeneration.
    path = run / "brief.html"
    w.write_text(path, path.read_text(encoding="utf-8").replace("does not establish", "establishes", 1))
    manifest = w.read(run / "manifest.json")
    manifest["hashes"]["brief.html"] = w.digest(path)
    w.write(run / "manifest.json", manifest)
    assert w.verify(run)["status"] == "withdrawn"


def test_format_eleven_reopens_without_editorial_rewrite(tmp_path):
    from uk_labour_market_navigator._report_v11 import render

    run, e = ready(tmp_path, "annual_gross")
    for name, text in render(w.read(run / "plan.json"), e, w.read(run / "synthesis.json")).items():
        w.write_text(run / name, text)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 11
    manifest["hashes"] = {n: w.digest(run / n) for n in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    assert w.verify(run)["status"] == "ready"
    assert before == {p.name: p.read_bytes() for p in run.iterdir()}
    assert "AI/host interpretation" in (run / "brief.html").read_text(encoding="utf-8")


def test_report_embeds_supplied_logo_and_detects_image_tampering(tmp_path):
    import base64
    import re

    run, _ = ready(tmp_path, "annual_gross")
    html = run / "brief.html"
    original = html.read_text(encoding="utf-8")
    image = re.search(r'src="data:image/png;base64,([^"]+)"', original)
    assert image is not None
    assert base64.b64decode(image[1]) == (Path(__file__).parents[1] / "assets/logo.png").read_bytes()
    assert original.count("<img ") == 1
    w.write_text(html, original.replace(image[1], "AAAA", 1))
    manifest = w.read(run / "manifest.json")
    manifest["hashes"]["brief.html"] = w.digest(html)
    w.write(run / "manifest.json", manifest)
    assert w.verify(run)["status"] == "withdrawn"


@pytest.mark.parametrize("measure", ["annual_gross", "hourly_excluding_overtime"])
def test_pay_definition_matches_selected_measure(tmp_path, measure):
    run, _ = ready(tmp_path, measure)
    for name in ("brief.html", "brief.md"):
        text = (run / name).read_text(encoding="utf-8")
        if measure == "annual_gross":
            assert "Tax year ending 5 April 2025" in text
            assert "Gross earnings include overtime and bonuses, before deductions" in text
            assert "historical earnings benchmark" in text
            assert "basic-salary offer" in text
        else:
            assert "Hourly earnings are before deductions and exclude overtime" in text
            assert "These gross earnings cover the tax year" not in text


def test_format_twelve_reopens_without_pay_definition_rewrite(tmp_path):
    from uk_labour_market_navigator._report_v12 import render

    run, e = ready(tmp_path, "annual_gross")
    for name, text in render(w.read(run / "plan.json"), e, w.read(run / "synthesis.json")).items():
        w.write_text(run / name, text)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 12
    manifest["hashes"] = {n: w.digest(run / n) for n in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    assert w.verify(run)["status"] == "ready"
    assert before == {p.name: p.read_bytes() for p in run.iterdir()}
