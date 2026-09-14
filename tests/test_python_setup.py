"""Bootstrap compatibility: a helpful exit before unsupported engine imports."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("version", [(3, 9, 6), (3, 10, 14)])
@pytest.mark.parametrize("command", ["setup", "help"])
def test_older_python_exits_before_engine_imports_without_creating_files(tmp_path, version, command):
    # Simulate version selection in an isolated supported process; this is not
    # a claim that the whole engine runs on these unsupported interpreters.
    script = f"""
import runpy, sys
sys.path.insert(0, {str(ROOT)!r})
sys.version_info = {version!r}
sys.argv = ['uk_labour_market_navigator', {command!r}]
try:
    runpy.run_module('uk_labour_market_navigator', run_name='__main__')
finally:
    assert 'uk_labour_market_navigator.workflow' not in sys.modules
    assert 'uk_labour_market_navigator.evidence' not in sys.modules
    assert 'uk_labour_market_navigator.adzuna_cli' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2
    assert not result.stdout
    assert "Python 3.11 or later" in result.stderr
    assert ".".join(map(str, version)) in result.stderr
    assert "continue my question" in result.stderr
    assert "Traceback" not in result.stderr
    assert not list(tmp_path.iterdir())


def test_bootstrap_syntax_parses_as_python_three_nine():
    for name in ("__init__.py", "__main__.py", "branding.py"):
        source = (ROOT / "uk_labour_market_navigator" / name).read_text(encoding="utf-8")
        ast.parse(source, feature_version=(3, 9))


@pytest.mark.parametrize("command", ["setup", "help"])
def test_supported_interpreter_continues_normal_onboarding(tmp_path, command):
    script = f"import sys,runpy;sys.path.insert(0,{str(ROOT)!r});sys.argv=['navigator',{command!r}];runpy.run_module('uk_labour_market_navigator',run_name='__main__')"
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stderr
    assert "Sheffield" in result.stdout if command == "setup" else "Show me an example" in result.stdout
    assert not list(tmp_path.iterdir())
