"""Real Git pipes must stay bounded when history exceeds OS pipe buffers."""

import subprocess
import sys
from pathlib import Path


def test_hygiene_consumes_large_history_without_pipe_deadlock(tmp_path):
    repo = tmp_path / "synthetic-history"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True, capture_output=True)
    for index in range(400):
        (repo / f"example-{index}.txt").write_text(str(index) + "x" * 1024, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Synthetic Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "Synthetic public fixtures",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    program = "from pathlib import Path; import sys; from scripts import check_hygiene; check_hygiene.ROOT = Path(sys.argv[1]); check_hygiene.main()"
    result = subprocess.run(
        [sys.executable, "-c", program, str(repo)],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert '"history_blobs": 400' in result.stdout
    assert '"findings": []' in result.stdout
