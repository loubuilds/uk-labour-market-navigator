"""Real V0.1 source and user-intent journeys, entirely offline."""

import socket
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from uk_labour_market_navigator import demand, evidence, pay
from uk_labour_market_navigator import workflow as w
from uk_labour_market_navigator._source import read_cells, snapshot
from uk_labour_market_navigator.report import md_text


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *a: pytest.fail("Official research must remain offline"))


def draft(facts):
    return {
        "title": "A useful workforce discussion",
        "opening": "Read workforce structure alongside the separately scoped demand and earnings evidence.",
        "sections": [
            {
                "heading": "What the evidence contributes",
                "text": "Use the source populations and periods to frame the discussion. Unmeasured requirements remain unanswered.",
                "fact_ids": [f["id"] for f in facts],
            }
        ],
        "next_questions": ["Would another district comparison help?"],
        "reviewed_by_host": True,
    }


def run_start(
    tmp_path,
    places=None,
    role="software developers",
    requested="software developers",
    gaps=None,
    workforce=True,
    advertising=True,
    earnings=True,
):
    return Path(
        w.start(
            "Explore " + requested + " for a hiring discussion",
            "Prepare a discussion",
            places or ["Reading"],
            role,
            gaps or [],
            tmp_path,
            release=True,
            requested_role=requested,
            include_workforce=workforce,
            include_demand=advertising,
            include_pay=earnings,
        )["run"]
    )


def finish(run, accept_pay=True):
    assert w.gather(run, True, accept_pay)["status"] == "awaiting_synthesis"
    e = w.read(run / "evidence.json")
    out = w.publish(run, draft(e["facts"]))
    assert out["status"] == "ready"
    assert w.verify(run)["status"] == "ready"
    return e, out


def test_combined_pay_and_source_provenance(tmp_path):
    run = run_start(tmp_path)
    assert w.gather(run, True)["status"] == "scope_choice"
    e, out = finish(run)
    f = next(f for f in e["pay"]["facts"] if f["id"] == "pay.median")
    assert f["value"] == "56914" and f["quality"]["cv_percent"] == "2.7"
    assert len(f["source_cells"]) == 2
    assert all(c["row"] == "86" and c["column"] == "D" for c in f["source_cells"])
    text = (run / "brief.html").read_text(encoding="utf-8")
    assert "UK-wide" in text and "2,030" in text and "338" in text and "56,914" in text
    assert "not a current local basic-salary offer" in text
    assert (run / "brief.md").read_text().count("## What this helps you assess") == 1


def test_pay_refusal_never_substitutes(tmp_path):
    e, out = finish(run_start(tmp_path), False)
    assert e["pay"]["facts"] == [] and e["pay"]["status"] == "declined"
    assert e["census"]["facts"] and e["demand"]["facts"]
    assert out["answerability"] == "accepted_scope_answered"


def test_requested_role_and_every_gap_survive(tmp_path):
    gaps = ["Requested geography outside the accepted districts remains unavailable.", "Travel time is unmeasured."]
    run = run_start(tmp_path, requested="Senior Java Developer", gaps=gaps)
    e, out = finish(run)
    context = w.read(run / "synthesis-context.json")
    assert context["requested_role"] == "Senior Java Developer"
    assert any("Java" in g for g in context["gaps"])
    assert any("Seniority" in g for g in context["gaps"])
    assert all(g in context["gaps"] and g in e["gaps"] for g in gaps)
    text = (run / "brief.html").read_text()
    assert "Senior Java Developer" in text and all(g in text for g in context["gaps"])
    assert out["answerability"] == "partial"


def test_zero_benchmark_real_occupations_retain_counts(tmp_path):
    body, ref = snapshot()
    cells = read_cells(body)
    codes = [c for (g, c), v in cells.items() if g == "K04000001" and Decimal(v["share"]) == 0]
    assert len(codes) == 78
    for code in codes:
        result = evidence.collect(evidence.resolve(["Reading"], code))
        if result["rows"]:
            assert result["rows"][0]["concentration"] is None
            assert any(f["id"].endswith(".count") for f in result["facts"])
            assert not any(f["id"].endswith(".concentration") for f in result["facts"])
    run = run_start(tmp_path, role="5411", requested="Upholsterers")
    e, out = finish(run)
    assert e["census"]["rows"][0]["count"] == "20"
    assert "rounds to zero" in (run / "brief.html").read_text()


@pytest.mark.parametrize("component", ["demand", "pay", "workforce"])
def test_numerical_component_failure_keeps_other_evidence(tmp_path, component):
    run = run_start(tmp_path)
    target = {"demand": demand, "pay": pay, "workforce": evidence}[component]
    with patch.object(target, "snapshot", side_effect=OSError("synthetic missing pack")):
        e, out = finish(run)
        key = {"workforce": "census"}.get(component, component)
        assert e[key]["facts"] == []
        assert all(e[k]["facts"] for k in {"census", "demand", "pay"} - {key})
        assert out["answerability"] == "partial"


def test_scotland_ni_and_demand_only_no_census_numeric_dependency(tmp_path):
    with patch.object(evidence, "snapshot", side_effect=AssertionError("Census not requested")):
        e, _ = finish(run_start(tmp_path, ["Edinburgh", "Belfast"], workforce=False, earnings=False))
        assert [r["new_adverts"] for r in e["demand"]["rows"]] == ["455", "489"]
    e, out = finish(run_start(tmp_path, ["Edinburgh", "Belfast"]))
    assert not e["census"]["facts"] and e["pay"]["facts"]
    assert "Census occupation evidence unavailable" in str(out["gaps"])


def test_london_demand_gap_preserves_workforce_pay(tmp_path):
    e, out = finish(run_start(tmp_path, ["Reading", "Westminster"]))
    assert not e["demand"]["facts"] and e["census"]["facts"] and e["pay"]["facts"]
    assert "Westminster" in str(out["gaps"])


def test_corrected_police_annual_pay_stays_missing(tmp_path):
    e, out = finish(run_start(tmp_path, role="3312", requested="Police officers"))
    assert not e["pay"]["facts"] and e["census"]["facts"]
    assert out["answerability"] == "partial"


def test_markdown_escapes_plain_fields_and_no_stale_report_copy(tmp_path):
    assert "\\[" in md_text("[example]")
    run = run_start(tmp_path, advertising=False, earnings=False)
    finish(run)
    text = (run / "brief.html").read_text()
    assert "Planned official-data integration" not in text
    assert "connect Adzuna" not in text
    run = run_start(tmp_path, ["Belfast"], workforce=False, earnings=False)
    finish(run)
    text = (run / "brief.html").read_text()
    assert "Census took place during" not in text


def test_pay_tampering_cannot_be_approved_by_run_hashes(tmp_path):
    run = run_start(tmp_path)
    finish(run)
    e = w.read(run / "evidence.json")
    e["pay"]["facts"][0]["value"] = "1"
    w.write(run / "evidence.json", e)
    seal = w.read(run / "evidence-seal.json")
    seal["evidence.json"] = w.digest(run / "evidence.json")
    w.write(run / "evidence-seal.json", seal)
    before = (run / "brief.html").read_bytes()
    assert w.verify(run)["status"] == "withdrawn"
    assert (run / "brief.html").read_bytes() == before


@pytest.mark.parametrize("family", ["workforce", "demand"])
def test_individual_reference_failure_keeps_other_families(tmp_path, family):
    from uk_labour_market_navigator import market

    run = run_start(tmp_path)
    target = market if family == "workforce" else demand
    with patch.object(target, "reference", side_effect=OSError("synthetic unreadable reference")):
        e, out = finish(run)
        key = "census" if family == "workforce" else "demand"
        assert not e[key]["facts"]
        assert all(e[k]["facts"] for k in {"census", "demand", "pay"} - {key})
        assert out["answerability"] == "partial"


def test_pay_quality_and_patterns_are_separate():
    from uk_labour_market_navigator.market import resolve_market

    role = resolve_market(["Reading"], "2134")["occupation"]
    scopes = [pay.option(role, pattern, measure) for pattern in pay.PATTERNS for measure in pay.MEASURES]
    for scope in scopes:
        result = pay.collect(scope)
        assert result["scope"] == scope
        assert all(
            f["unit"] == ("GBP/year" if scope["measure"] == "annual_gross" else "GBP/hour") for f in result["facts"]
        )
    for raw, cv in [("x", "2.0"), ("100", "x"), ("100", "20.1")]:
        assert pay.cell_quality({"raw_value": raw, "raw_cv": cv, "value_precision": 0})[0] is None
    wrong = {**scopes[0], "geography_id": "E06000038"}
    with pytest.raises(ValueError):
        pay.collect(wrong)


def test_four_locations_require_smaller_explicit_scope(tmp_path):
    with pytest.raises(evidence.ScopeChoice):
        run_start(tmp_path, ["Reading", "Cambridge", "Edinburgh", "Belfast"])


def test_demand_reference_missing_before_planning(tmp_path):
    with patch.object(demand, "reference", side_effect=OSError("synthetic missing demand reference")):
        e, out = finish(run_start(tmp_path))
        assert not e["demand"]["facts"] and e["census"]["facts"] and e["pay"]["facts"]
        assert out["answerability"] == "partial"


def test_pay_report_names_exact_measure_and_source_title(tmp_path):
    run = Path(
        w.start(
            "Explore earnings",
            "Prepare a discussion",
            ["Reading"],
            "2472",
            [],
            tmp_path,
            release=True,
            include_workforce=False,
            include_pay=True,
            pay_measure="hourly_excluding_overtime",
        )["run"]
    )
    e, out = finish(run)
    html = (run / "brief.html").read_text(encoding="utf-8")
    summary = html.split("Official earnings", 1)[1].split("What to take", 1)[0]
    assert "hourly earnings excluding overtime" in summary
    assert e["pay"]["scope"]["source_occupation_label"] in summary
    assert "source title differs" in summary


def test_scotland_proposal_does_not_promise_census(tmp_path):
    result = w.start(
        "Explore software development",
        "Prepare a discussion",
        ["Edinburgh"],
        "2134",
        [],
        tmp_path,
        release=True,
        include_demand=True,
        include_pay=True,
    )
    assert "does not cover City of Edinburgh" in result["proposal"]
    assert "will remain unanswered" in result["proposal"]


def test_interrupted_publish_remains_retriable(tmp_path):
    run = run_start(tmp_path)
    w.gather(run, True, True)
    e = w.read(run / "evidence.json")
    original = w.write_text

    def fail_markdown(path, content):
        if path.name == "brief.md":
            raise OSError("synthetic rendering interruption")
        return original(path, content)

    with patch.object(w, "write_text", side_effect=fail_markdown), pytest.raises(OSError):
        w.publish(run, draft(e["facts"]))
    assert w.verify(run)["status"] == "incomplete"
    assert w.read(run / "state.json")["stage"] == "synthesis"
    assert w.publish(run, draft(e["facts"]))["status"] == "ready"


def test_saved_version_four_keeps_its_original_rendering(tmp_path):
    from uk_labour_market_navigator._report_v4 import render as prior_render

    run = run_start(tmp_path)
    e, _ = finish(run)
    plan = w.read(run / "plan.json")
    synthesis = w.read(run / "synthesis.json")
    for name, content in prior_render(plan, e, synthesis).items():
        w.write_text(run / name, content)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 4
    manifest["hashes"] = {name: w.digest(run / name) for name in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = (run / "brief.html").read_bytes()
    assert w.verify(run)["status"] == "ready"
    assert (run / "brief.html").read_bytes() == before
    assert b"Sampling uncertainty (CV)" not in before


def test_current_pay_report_explains_cv(tmp_path):
    run = run_start(tmp_path)
    finish(run)
    html = (run / "brief.html").read_text(encoding="utf-8")
    assert "Sampling uncertainty (CV)" not in html
    assert "CV (coefficient of variation) indicates the precision" in html
    assert "A lower percentage means greater precision" in html
    assert w.read(run / "manifest.json")["version"] == 15


def test_current_chart_has_no_corrupted_separator(tmp_path):
    from uk_labour_market_navigator.report import chart

    run = run_start(tmp_path, ["Reading", "Cambridge"])
    e, out = finish(run)
    html = (run / "brief.html").read_text(encoding="utf-8")
    assert "\u00c2" not in html and "\ufffd" not in html
    assert "&middot; Census 2021" in chart(e["census"]["rows"])


def test_tool_credit_is_unlinked_in_footer_without_verification_homework(tmp_path):
    run = run_start(tmp_path)
    finish(run)
    html = (run / "brief.html").read_text(encoding="utf-8")
    md = (run / "brief.md").read_text(encoding="utf-8")
    assert (
        html.count("Tool designed and built by Louise Mead.")
        == md.count("Tool designed and built by Louise Mead.")
        == 1
    )
    assert "Tool designed and built by Louise Mead." not in html.split("</header>")[0]
    footer = html.split("<footer>")[1]
    assert 'href="https://github.com/loubuilds"' in footer
    assert 'Tool designed and built by Louise Mead. <a href="https://github.com/loubuilds">' in footer
    assert "Explore Louise&#x27;s work on GitHub</a>" in footer
    assert "Tool designed and built by Louise Mead. [Explore Louise's work on GitHub]" in md
    assert "ask your coding assistant to verify this report" not in footer
    assert "does not fetch newer data" not in footer
    assert "Open Government Licence v3.0" in footer
    assert "cannot verify itself" not in html
