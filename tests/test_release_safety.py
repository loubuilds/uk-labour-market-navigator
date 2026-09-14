"""V0.1 regression cases use isolated temporary folders only."""

from pathlib import Path
from unittest.mock import patch

import pytest

from uk_labour_market_navigator import workflow as w


def start(tmp_path):
    return Path(
        w.start(
            "Explain developer employment",
            "Prepare a discussion",
            ["Reading"],
            "software developers",
            ["Java specialism", "Seniority", "Commuting reach"],
            tmp_path,
        )["run"]
    )


def contents(path):
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def test_unrelated_folder_files_and_missing_identity_never_mutated(tmp_path):
    (tmp_path / "brief.html").write_text("unrelated report")
    (tmp_path / "brief.md").write_text("unrelated notes")
    before = contents(tmp_path)
    assert w.verify(tmp_path)["status"] == "withdrawn"
    assert contents(tmp_path) == before
    run = start(tmp_path)
    (run / "run-identity.json").unlink()
    before = contents(run)
    assert w.verify(run)["status"] == "withdrawn"
    assert contents(run) == before
    assert w.verify(tmp_path / "brief.html")["status"] == "withdrawn"


@pytest.mark.parametrize("collected", [False, True])
def test_unfinished_run_check_is_read_only_and_continuable(tmp_path, collected):
    run = start(tmp_path)
    if collected:
        w.gather(run, True)
    before = contents(run)
    assert w.verify(run)["status"] == "incomplete"
    assert contents(run) == before
    if not collected:
        assert w.gather(run, True)["status"] == "awaiting_synthesis"


def test_explicit_gaps_reach_synthesis_context(tmp_path):
    run = start(tmp_path)
    w.gather(run, True)
    assert w.read(run / "synthesis-context.json")["gaps"] == w.read(run / "plan.json")["gaps"]


def test_interrupted_collection_keeps_retriable_state(tmp_path):
    run = start(tmp_path)
    original = w.write

    def fail_context(path, value):
        if path.name == "synthesis-context.json":
            raise OSError("synthetic interruption")
        original(path, value)

    with patch.object(w, "write", side_effect=fail_context), pytest.raises(OSError):
        w.gather(run, True)
    assert w.read(run / "state.json")["stage"] == "scope_choice"
    assert w.gather(run, True)["status"] == "awaiting_synthesis"


def test_atomic_replace_failure_preserves_previous_file(tmp_path):
    target = tmp_path / "example.json"
    w.write(target, {"before": True})
    before = target.read_bytes()
    with patch.object(Path, "replace", side_effect=OSError("synthetic interruption")), pytest.raises(OSError):
        w.write(target, {"after": True})
    assert target.read_bytes() == before
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize(
    "text",
    [
        "![image](//example.invalid/pixel)",
        "<img src=x>",
        "[link](javascript:alert)",
        "token=synthetic_placeholder",
        "Contact 07700 900123",
        "Read /home/synthetic/private",
    ],
)
def test_public_text_refuses_active_markup_and_private_shapes(text):
    with pytest.raises(ValueError):
        w.public_text(text)
