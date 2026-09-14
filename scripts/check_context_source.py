"""Reproduce context and trace literal original records independently of extractors."""

import csv
import io
import json
import zipfile
from pathlib import Path

from uk_labour_market_navigator import context, context_source, economic
from uk_labour_market_navigator.market import resolve_market

ROOT = Path(__file__).resolve().parents[1]


def main():
    records, ref = context_source.snapshot()
    original = ROOT / "uk_labour_market_navigator" / "resources"
    traces = []
    with zipfile.ZipFile(original / "context-sources.zip") as archive:
        # Hand-traced CSV line numbers are independent of production key selection.
        expected = {
            "aps.csv": [
                (674, "E08000019", "71.6"),
                (675, "E08000019", "278000"),
                (676, "E08000019", "388400"),
                (677, "E08000019", "3.3"),
                (682, "E08000019", "24.6"),
                (685, "E08000019", "3.1"),
                (4202, "K02000001", "75.4"),
                (4205, "K02000001", "0.3"),
                (4206, "K02000001", "4.4"),
                (4209, "K02000001", "0.1"),
                (4210, "K02000001", "21.0"),
                (4213, "K02000001", "0.2"),
            ],
            "claimants.csv": [
                (114, "E08000019", "16715"),
                (115, "E08000019", "4.4"),
                (725, "K02000001", "3.9"),
                (839, "E08000019", "4.4"),
                (1449, "K02000001", "3.8"),
            ],
            "unemployment.csv": [(114, "E08000019", "5.2"), (115, "E08000019", "1.4")],
        }
        for name, checks in expected.items():
            rows = list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig"))))
            for line, geo, value in checks:
                row = rows[line - 2]
                assert row["GEOGRAPHY_CODE"] == geo and row["OBS_VALUE"] == value
                assert row["OBS_STATUS"] == "A" and row["OBS_CONF"] == "F"
                assert row["GEOGRAPHY_TYPECODE"] == ("499" if geo == "K02000001" else "424")
                traces.append({"source": name, "line": line, "geography": geo, "value": value, "urn": row["URN"]})
    base = resolve_market(["Sheffield"], "7219")
    collected = context.collect(context_source.resolve_scope(base), base)
    by_id = {f["id"]: f for f in collected["facts"]}
    for suffix, local, uk in [
        ("claimant_rate", "4.4", "3.9"),
        ("claimant_change", "0.0", "0.1"),
        ("employment_rate", "71.6", "75.4"),
        ("inactivity_rate", "24.6", "21.0"),
        ("unemployment_rate", "5.2", "4.4"),
    ]:
        assert by_id["E08000019.context_" + suffix]["value"] == local
        assert by_id["K02000001.context_" + suffix]["value"] == uk
    assert (
        by_id["E08000019.context_unemployment_rate"]["source_cells"][0]["raw"]["ITEM_NAME"]
        == "Unemployment rate (model based)"
    )
    with zipfile.ZipFile(original / "economic-sources.zip") as archive:
        for code, line, period, value in [
            ("l55o", 646, "2026 JUL", "3.1"),
            ("d7g7", 646, "2026 JUL", "2.9"),
            ("kai9", 312, "2026 JUN", "3.5"),
            ("kac3", 312, "2026 JUN", "4.1"),
        ]:
            rows = list(csv.reader(io.StringIO(archive.read(code + ".csv").decode("utf-8-sig"))))
            assert rows[line - 1] == [period, value]
            assert rows[1] == ["CDID", code.upper()] and rows[4] == ["Unit", "%"]
            traces.append({"source": code + ".csv", "line": line, "period": period, "value": value})
    national = economic.collect(economic.resolve_scope())
    assert [f["value"] for f in national["facts"]] == ["3.1", "2.9", "3.5", "4.1"]
    print(
        json.dumps(
            {
                "status": "passed",
                "context_edition": ref["version"],
                "rows": {k: len(v) for k, v in records.items()},
                "districts": len(ref["places"]),
                "economic_edition": economic.VERSION,
                "manual_original_source_traces": traces,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
