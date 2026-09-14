"""Reproduce the ASHE pack and independently trace selected raw XML cells."""

import io
import json
import zipfile
from xml.etree import ElementTree as ET

from uk_labour_market_navigator import pay
from uk_labour_market_navigator._pay_source import PAY_VERSION, encode_pack, extract_pay
from uk_labour_market_navigator._source import sha256
from uk_labour_market_navigator.identities import reference


def require(condition, message):
    if not condition:
        raise ValueError(message)


def xml_cells(body, sheet):
    # Deliberately independent of the production worksheet reader and extractor.
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = ["".join(n.itertext()) for n in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        sheets = ET.fromstring(z.read("xl/workbook.xml")).find("s:sheets", ns)
        chosen = next(n for n in sheets if n.attrib["name"] == sheet)
        rid = chosen.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = next(
            n.attrib["Target"] for n in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")) if n.attrib["Id"] == rid
        )
        path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        values = {}
        for c in ET.fromstring(z.read(path)).findall(".//s:c", ns):
            value = c.findtext("s:v", default="", namespaces=ns)
            if c.attrib.get("t") == "s":
                value = strings[int(value)]
            elif c.attrib.get("t") == "inlineStr":
                value = "".join(c.find("s:is", ns).itertext())
            values[c.attrib["r"]] = value
        return values


def main():
    records, ref = pay.snapshot()
    body = (pay.RESOURCES / "ashe14.zip").read_bytes()
    require(sha256(body) == ref["source"]["sha256"], "ASHE archive hash differs")
    actual = extract_pay(body, 14)
    require(actual == records and len(actual) == 2472, "ASHE rows differ")
    require({r["occupation_code"] for r in actual.values()} == set(reference()["occupations"]), "ASHE taxonomy differs")
    require(
        encode_pack({"schema_version": 1, "version": PAY_VERSION, "records": actual})
        == (pay.RESOURCES / "pay.json.gz").read_bytes(),
        "ASHE pack bytes differ",
    )
    oracles = [
        ("2134", 86, "56914", "2.7"),
        ("7211", 454, "27035", "3.3"),
        ("2421", 152, "50062", "6.5"),
        ("3312", 225, "x", "x"),
    ]
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        prefix = "ashetable142025provisional/PROV - Occupation SOC20 (4) Table "
        estimates = xml_cells(z.read(prefix + "14.7a   Annual pay - Gross 2025.xlsx"), "Full-Time")
        quality = xml_cells(z.read(prefix + "14.7b   Annual pay - Gross 2025 CV.xlsx"), "Full-Time")
    traces = []
    for code, row, value, cv in oracles:
        require(estimates["B" + str(row)] == quality["B" + str(row)] == code, "Raw XML occupation mismatch")
        require(estimates["D" + str(row)] == value and quality["D" + str(row)] == cv, "Raw XML median/CV mismatch")
        traces.append({"soc2020": code, "row": row, "column": "D", "sheet": "Full-Time", "estimate": value, "cv": cv})
    print(
        json.dumps(
            {
                "status": "passed",
                "records": len(actual),
                "taxonomy": "SOC2020",
                "archive_sha256": ref["source"]["sha256"],
                "independent_xml_traces": traces,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
