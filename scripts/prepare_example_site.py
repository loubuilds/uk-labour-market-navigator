"""Prepare only the verified fictional HTML example for static hosting."""

import argparse
import shutil
from pathlib import Path

from .make_example import ROOT, generate


def prepare(output):
    generate(check=True)
    # Require a fresh directory so unrelated files cannot enter the deployment.
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(ROOT / "examples" / "brief.html", output / "index.html")
    print("PASS: static example prepared; nothing deployed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new local directory")
    prepare(parser.parse_args().output)


if __name__ == "__main__":
    main()
