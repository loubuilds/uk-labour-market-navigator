"""Reproduce paid hours and trace independently selected original workbook cells."""

import json
import zipfile

from uk_labour_market_navigator import hours, pay
from uk_labour_market_navigator._pay_source import encode_pack
from uk_labour_market_navigator._source import sha256

from .check_pay_source import require, xml_cells


def main():
    body = (hours.RESOURCES / "ashe14.zip").read_bytes()
    ref = json.loads((hours.RESOURCES / "pay-reference.json").read_bytes())
    require(sha256(body) == ref["source"]["sha256"], "ASHE original archive differs")
    actual = hours.extract(body)
    require(actual == hours.snapshot(), "Paid-hours snapshot differs from original source")
    require(
        encode_pack({"schema_version": 1, "version": hours.VERSION, "records": actual})
        == (hours.RESOURCES / "hours.json.gz").read_bytes(),
        "Paid-hours snapshot bytes differ",
    )
    traces = []
    with zipfile.ZipFile(hours.RESOURCES / "ashe14.zip") as z:
        for measure, number, name, median, mean in (
            ("basic", "10", "Basic", "37.3", "37.2"),
            ("total", "9", "Total", "37.4", "37.8"),
            ("overtime", "11", "Overtime", "2.3", "0.6"),
        ):
            prefix = "ashetable142025provisional/PROV - Occupation SOC20 (4) Table 14."
            a = xml_cells(z.read(prefix + number + "a   Paid hours worked - " + name + " 2025.xlsx"), "Full-Time")
            b = xml_cells(z.read(prefix + number + "b   Paid hours worked - " + name + " 2025 CV.xlsx"), "Full-Time")
            require(a["B458"] == b["B458"] == "7219", "Independent hours SOC differs")
            for stat, column, expected in (("median", "D", median), ("mean", "F", mean)):
                pair = actual["7219/full_time/" + measure]["values"][stat]
                require(
                    pair["raw_value"] == a[column + "458"] and pair["raw_cv"] == b[column + "458"],
                    "Independent hours/CV cell mismatch",
                )
                value, cv, quality = pay.cell_quality(pair)
                require(str(value) == expected, "Independent displayed hours mismatch")
                traces.append(
                    {
                        "measure": measure,
                        "statistic": stat,
                        "cell": column + "458",
                        "soc2020": "7219",
                        "sheet": "Full-Time",
                        "hours": str(value),
                        "cv_percent": str(cv),
                        "quality": quality,
                    }
                )
    print(json.dumps({"status": "passed", "records": len(actual), "independent_xml_traces": traces}, indent=2))


if __name__ == "__main__":
    main()
