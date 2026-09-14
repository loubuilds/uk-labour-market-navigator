"""Reproductions of independent pre-publication findings, without real accounts."""

import json
import os
from pathlib import Path

import pytest

from uk_labour_market_navigator import adzuna_cli, provider_support
from uk_labour_market_navigator import workflow as w
from uk_labour_market_navigator.__main__ import main
from uk_labour_market_navigator.report import md_text


def prepare(tmp_path, *, question="Explore software developers", places=None, gaps=None, pay=True):
    result = w.start(
        question,
        "Prepare a discussion",
        places or ["Reading"],
        "2134",
        gaps or [],
        tmp_path,
        release=True,
        include_demand=True,
        include_pay=pay,
    )
    return result, Path(result["run"])


def finish(run, accepted_pay=True):
    w.gather(run, True, accepted_pay)
    facts = w.read(run / "evidence.json")["facts"]
    draft = {
        "title": "Occupation context",
        "opening": "A starting view of the occupation.",
        "sections": [
            {
                "heading": "Workforce context",
                "text": "These are dated occupation observations.",
                "fact_ids": [facts[0]["id"]],
            }
        ],
        "next_questions": ["Would a comparison with Cambridge help?"],
        "reviewed_by_host": True,
    }
    return w.publish(run, draft)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction regression")
def test_real_junction_and_ancestor_refused_without_writes(tmp_path):
    import _winapi

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    _winapi.CreateJunction(str(target), str(link))
    try:
        for guard in (w.unlinked, provider_support.unlinked):
            with pytest.raises(ValueError):
                guard(link / "child" / "run")
        with pytest.raises(ValueError):
            prepare(link / "runs")
        assert list(target.iterdir()) == []
    finally:
        # Remove just the junction itself, never recursively touch its target.
        link.rmdir()
    assert target.is_dir()


@pytest.mark.skipif(os.name != "nt", reason="Windows NUL regression")
def test_nul_input_refused_before_any_store_or_prompt(tmp_path, monkeypatch, capsys):
    def forbidden():
        pytest.fail("Redirected input must not access a native store")

    monkeypatch.setattr(adzuna_cli, "_keyring", forbidden)
    with open(os.devnull) as stream:
        monkeypatch.setattr(adzuna_cli.sys, "stdin", stream)
        assert not adzuna_cli.interactive_console()
        assert main(["adzuna", "connect", "--permission", "personal_research"]) == 2
    assert "interactive local terminal" in capsys.readouterr().out


def test_specialist_gaps_are_in_spoken_proposal(tmp_path):
    result, _ = prepare(tmp_path, question="Explore Senior Java Developers")
    assert "Java specialism is not measured" in result["proposal"]
    assert "Seniority is not measured" in result["proposal"]


def test_unavailable_scope_has_separate_advertising_bullet(tmp_path):
    result, _ = prepare(tmp_path, places=["Edinburgh", "Belfast"])
    assert "continues.\n- Advertising:" in result["proposal"]


def test_pay_only_proposal_does_not_claim_district_evidence(tmp_path):
    result = w.start(
        "Explore pay",
        "Prepare a discussion",
        ["Reading"],
        "2134",
        [],
        tmp_path,
        release=True,
        include_workforce=False,
        include_pay=True,
    )
    assert "in Reading" not in result["proposal"] and "UK-wide" in result["proposal"]


def test_declined_pay_separate_from_gaps_and_chat_facts_are_exact(tmp_path):
    _, run = prepare(tmp_path)
    result = finish(run, False)
    assert result["answerability"] == "accepted_scope_answered" and result["gaps"] == []
    assert result["declined_components"] == ["UK pay"]
    evidence = w.read(run / "evidence.json")
    assert result["checked_facts"] == [{"id": f["id"], "display": f["display"]} for f in evidence["facts"]]
    assert any("2.30" in f["display"] for f in result["checked_facts"] if f["id"].endswith("concentration"))
    html = (run / "brief.html").read_text(encoding="utf-8")
    assert "What remains open" not in html and "UK pay was left out as you chose" in html
    assert "<ul></ul>" not in html


def test_declining_pay_does_not_remove_explicit_original_pay_requirement(tmp_path):
    gap = "Local role pay was requested and remains unavailable."
    _, run = prepare(tmp_path, gaps=[gap])
    result = finish(run, False)
    assert result["answerability"] == "partial" and result["gaps"] == [gap]


def test_old_format_eight_replays_unchanged(tmp_path):
    from uk_labour_market_navigator._report_v8 import render

    _, run = prepare(tmp_path)
    finish(run, False)
    for name, text in render(
        w.read(run / "plan.json"), w.read(run / "evidence.json"), w.read(run / "synthesis.json")
    ).items():
        w.write_text(run / name, text)
    manifest = w.read(run / "manifest.json")
    manifest["version"] = 8
    manifest["hashes"] = {name: w.digest(run / name) for name in manifest["hashes"]}
    w.write(run / "manifest.json", manifest)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    assert w.verify(run)["status"] == "ready"
    assert w.verify(run)["answerability"] == "partial"
    assert before == {p.name: p.read_bytes() for p in run.iterdir()}


def test_non_utf8_draft_has_sanitised_cli_error(tmp_path, capsys):
    _, run = prepare(tmp_path)
    w.gather(run, True, True)
    draft = tmp_path / "draft.json"
    draft.write_text('{"text":"synthetic-private-phrase"}', encoding="utf-16")
    assert main(["publish", str(run), "--draft", str(draft)]) == 2
    message = json.loads(capsys.readouterr().out)["message"]
    assert "codec" not in message and "synthetic-private-phrase" not in message
    assert w.verify(run)["status"] == "incomplete"


def test_markdown_readable_without_enabling_markup():
    assert md_text("Reading (2.3%).") == "Reading (2.3%)."
    assert md_text("[label](target)") == r"\[label\](target)"
    for value in ("# heading", "- list", "+ list", "1. ordered", "---"):
        assert "\\" in md_text(value)
