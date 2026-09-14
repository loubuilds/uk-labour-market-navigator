"""System-style temp aliases work without accepting links in research paths."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_install, make_example
from uk_labour_market_navigator import workflow as w


@contextmanager
def directory_alias(link, target):
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)
    try:
        yield link
    finally:
        # Remove just the link, never recursively remove its target.
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


@pytest.fixture
def aliased_temp(tmp_path, monkeypatch):
    physical = tmp_path / "physical"
    physical.mkdir()
    with directory_alias(tmp_path / "system-alias", physical) as alias:
        monkeypatch.setattr(tempfile, "tempdir", str(alias))
        yield alias, physical
    assert physical.is_dir()


def test_example_reproduces_through_system_style_temp_alias(aliased_temp):
    # Exercises the actual production call site, including publication/replay.
    _, physical = aliased_temp
    make_example.generate(check=True)
    assert list(physical.iterdir()) == []


def test_install_harness_uses_physical_temp_root(aliased_temp, tmp_path, monkeypatch):
    alias, physical = aliased_temp
    created, commands = [], []

    def create(env):
        assert env.is_relative_to(physical)
        w.unlinked(env)
        created.append(env)

    def run(args, *, cwd, **kwargs):
        assert cwd.is_relative_to(physical)
        assert not cwd.is_relative_to(alias)
        w.unlinked(cwd)
        commands.append(args)
        return SimpleNamespace(
            stdout="UK Labour Market Navigator\nEvidence-led labour market research companion for People and Talent practitioners."
        )

    monkeypatch.setattr(check_install.venv, "EnvBuilder", lambda **kwargs: SimpleNamespace(create=create))
    monkeypatch.setattr(check_install.subprocess, "run", run)
    check_install.main(tmp_path / "synthetic.whl")
    assert len(created) == 1 and len(commands) == 3
    assert list(physical.iterdir()) == []


def test_only_owned_root_is_normalised_internal_links_still_refused(aliased_temp):
    _, physical = aliased_temp
    with tempfile.TemporaryDirectory() as temporary:
        raw = Path(temporary)
        with pytest.raises(ValueError, match="unlinked"):
            w.unlinked(raw / "runs")
        root = raw.resolve(strict=True)
        assert root.is_relative_to(physical)
        runs = root / "runs"
        result = w.start("A workforce overview", "Explore local work", ["Sheffield"], "7219", [], runs)
        assert w.verify(Path(result["run"]))["status"] == "incomplete"
        outside = root / "outside"
        outside.mkdir()
        marker = outside / "marker.json"
        marker.write_text('{"unchanged": true}', encoding="utf-8")
        with directory_alias(runs / "redirect", outside) as internal:
            for operation in (
                lambda: w.read(internal / "marker.json"),
                lambda: w.write(internal / "marker.json", {}),
                lambda: w.start("A workforce overview", "Explore local work", ["Sheffield"], "7219", [], internal),
            ):
                with pytest.raises(ValueError, match="unlinked"):
                    operation()
            assert marker.read_text(encoding="utf-8") == '{"unchanged": true}'
            assert list(outside.iterdir()) == [marker]
