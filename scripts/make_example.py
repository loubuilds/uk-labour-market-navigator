"""Generate or independently replay the tracked generic V0.1 demonstration."""

import argparse
import tempfile
from pathlib import Path

from uk_labour_market_navigator import workflow as w

from .example_preview import preview

ROOT = Path(__file__).resolve().parents[1]


def generate(check=False):
    folder = ROOT / "examples"
    request = w.read(folder / "request.json")
    if request["scope_accepted"] is not True or request["uk_full_time_annual_pay_accepted"] is not True:
        raise ValueError("The synthetic example must declare its demonstration scopes")
    draft = w.read(folder / "synthesis.json")
    with tempfile.TemporaryDirectory(prefix="uk-labour-market-navigator-example-") as temporary:
        result = w.start(
            request["question"],
            request["purpose"],
            request["places"],
            request["role"],
            request["gaps"],
            Path(temporary).resolve(strict=True),
            release=True,
            requested_role=request["requested_role"],
            include_demand=True,
            include_pay=True,
            include_hours=request["uk_paid_hours_accepted"],
            include_context=request["wider_context_accepted"],
        )
        run = Path(result["run"])
        if w.gather(run, True, True)["status"] != "awaiting_synthesis":
            raise ValueError("Example collection failed")
        if w.publish(run, draft)["status"] != "ready" or w.verify(run)["status"] != "ready":
            raise ValueError("Example verification failed")
        outputs = {name: (run / name).read_bytes() for name in ("plan.json", "evidence.json", "brief.html", "brief.md")}
        outputs["preview.svg"] = preview(outputs["brief.html"].decode("utf-8"), w.read(run / "plan.json")).encode(
            "utf-8"
        )
        for name, body in outputs.items():
            if check:
                if not (folder / name).exists() or (folder / name).read_bytes() != body:
                    raise ValueError("Tracked example differs: " + name)
            else:
                (folder / name).write_bytes(body)
    print(
        "PASS: generic example collected, rendered and independently reverified"
        + ("; tracked files match" if check else "")
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    generate(parser.parse_args().check)


if __name__ == "__main__":
    main()
