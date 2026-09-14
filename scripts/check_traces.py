"""Independently inspect selected original XML cells without runtime extraction."""

import io
import json
import zipfile
from xml.etree import ElementTree as ET

from uk_labour_market_navigator._source import RESOURCES


def inspect(body, sheet_name, expected):
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    wanted_rows = {int("".join(c for c in key if c.isdigit())) for key in expected}
    found = {}
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        strings = ["".join(n.itertext()) for n in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        sheet = next(
            n for n in ET.fromstring(z.read("xl/workbook.xml")).find("s:sheets", ns) if n.attrib["name"] == sheet_name
        )
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = next(
            n.attrib["Target"] for n in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")) if n.attrib["Id"] == rid
        )
        path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        with z.open(path) as stream:
            for _, row in ET.iterparse(stream, events=("end",)):
                if row.tag != "{" + ns["s"] + "}row":
                    continue
                number = int(row.attrib["r"])
                if number in wanted_rows:
                    for cell in row:
                        key = cell.attrib["r"]
                        if key in expected:
                            value = cell.findtext("s:v", default="", namespaces=ns)
                            found[key] = strings[int(value)] if cell.attrib.get("t") == "s" else value
                row.clear()
                if number >= max(wanted_rows):
                    break
    if found != expected:
        raise ValueError("Independent source-cell trace differs in sheet " + sheet_name)
    return {"sheet": sheet_name, "cells": found}


def main():
    census = (RESOURCES / "source.xlsx").read_bytes()
    traces = [
        inspect(census, "1", {"A9914": "2134", "C9914": "Total population", "D9914": "264070", "E9914": "1"}),
        inspect(
            census,
            "3",
            {
                "A14488": "2134",
                "C14488": "E06000038",
                "D14488": "Reading",
                "E14488": "2030",
                "F14488": "2.2999999999999998",
                "A24376": "2134",
                "C24376": "E07000008",
                "D24376": "Cambridge",
                "E24376": "3165",
                "F24376": "4.5",
            },
        ),
    ]
    expected = {}
    for row, code, value in [
        (20906, "E07000008", "705"),
        (53697, "N09000003", "489"),
        (57354, "S12000036", "455"),
        (71999, "E06000038", "338"),
    ]:
        expected.update({"D" + str(row): "2134", "F" + str(row): code, "AR" + str(row): value})
    traces.append(inspect((RESOURCES / "labourdemandbyoccupation.xlsx").read_bytes(), "Table 5", expected))
    print(
        json.dumps(
            {
                "status": "passed",
                "method": "Independent selected original XML cells, not the production reader or derived pack",
                "traces": traces,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
