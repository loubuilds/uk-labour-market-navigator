"""Repeatable local V0.1 release gate; does not contact any provider."""

import hashlib
import json
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    receipt = {
        "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "checks": [],
    }
    target = ROOT / "runs" / "release-validation.json"
    target.parent.mkdir(exist_ok=True)

    def run(label, args):
        completed = subprocess.run(
            [sys.executable, *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True
        )
        receipt["checks"].append(
            {
                "check": label,
                "exit_code": completed.returncode,
                "output": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
        )
        print(label + ": " + ("PASS" if completed.returncode == 0 else "FAIL"), flush=True)
        if completed.returncode:
            print(completed.stdout.strip(), flush=True)
            print(completed.stderr.strip(), file=sys.stderr, flush=True)
            raise RuntimeError(label + " failed; inspect the local validation receipt")

    try:
        for label, args in [
            ("tests", ["-m", "pytest", "-q", "-p", "no:cacheprovider"]),
            ("lint", ["-m", "ruff", "check", "--no-cache", "uk_labour_market_navigator", "scripts", "tests"]),
            (
                "format",
                ["-m", "ruff", "format", "--check", "--no-cache", "uk_labour_market_navigator", "scripts", "tests"],
            ),
            ("census_and_identities", ["-m", "scripts.check_source"]),
            ("advertising", ["-m", "scripts.check_demand_source"]),
            ("pay", ["-m", "scripts.check_pay_source"]),
            ("paid_hours", ["-m", "scripts.check_hours_source"]),
            ("wider_context", ["-m", "scripts.check_context_source"]),
            ("independent_source_traces", ["-m", "scripts.check_traces"]),
            ("worked_example", ["-m", "scripts.make_example", "--check"]),
            ("hygiene", ["-m", "scripts.check_hygiene"]),
        ]:
            run(label, args)
        output = ROOT / "dist" / "v0.1rc6"
        output.mkdir(parents=True, exist_ok=True)
        run("build", ["-m", "build", "--no-isolation", "--outdir", str(output)])
        wheels = list(output.glob("*.whl"))
        archives = list(output.glob("*.tar.gz"))
        if len(wheels) != 1 or len(archives) != 1:
            raise ValueError("Expected one wheel and one source distribution")
        wheel = wheels[0]
        required = {
            "uk_labour_market_navigator/resources/" + n
            for n in [
                "source.xlsx",
                "census2021.csv.gz",
                "soc2020.zip",
                "reference.json",
                "identities.json",
                "advertising-reference.json",
                "advertising.json.gz",
                "labourdemandbyoccupation.xlsx",
                "ashe14.zip",
                "pay-reference.json",
                "pay.json.gz",
                "hours.json.gz",
                "context-reference.json",
                "context-sources.zip",
                "economic-reference.json",
                "economic-sources.zip",
            ]
        }
        with zipfile.ZipFile(wheel) as z:
            names = z.namelist()
            if not required.issubset(names) or any(n.startswith(("runs/", ".venv/", "private/")) for n in names):
                raise ValueError("Wheel contents violate the public package contract")
            metadata = z.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode()
            if "License-Expression: AGPL-3.0-only AND OGL-UK-3.0 AND CC-BY-SA-4.0" not in metadata:
                raise ValueError("Wheel licence metadata is incorrect")
            lic = next(n for n in names if n.endswith("/licenses/LICENSE"))
            if z.read(lic) != (ROOT / "LICENSE").read_bytes():
                raise ValueError("Distributed licence differs")
        with tarfile.open(archives[0]) as tar:
            names = tar.getnames()
            if any("/.venv/" in n or "/runs/" in n or "/private/" in n for n in names):
                raise ValueError("Source archive contains excluded files")
        receipt["artifacts"] = [
            {"file": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in [wheel, archives[0]]
        ]
        run("clean_offline_install", ["-m", "scripts.check_install", str(wheel)])
        receipt["status"] = "passed"
    except Exception:
        receipt["status"] = "failed"
        raise
    finally:
        target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("PASS: all automated release checks; usability and publication privacy reviews remain separate.")


if __name__ == "__main__":
    main()
