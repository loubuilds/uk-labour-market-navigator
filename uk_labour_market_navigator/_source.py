"""Pinned official Census cells; no model, network or inferred denominators."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

RESOURCES = Path(__file__).parent / "resources"
DATASET = "ons_census2021_occupation_2023"
PERIOD = "2021-03-21"
POPULATION = "Usual residents aged 16 years and over in employment in the week before Census Day"
SOURCE_PAGE = (
    "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/"
    "occupationsofthoseinemploymentbylocalareaworkingpatternemploymentstatusanddisabilitystatusenglandandwalescensus2021"
)
SOURCE_URL = SOURCE_PAGE.replace("https://www.ons.gov.uk", "https://www.ons.gov.uk/file?uri=") + (
    "/2021/censusoccupationsenglandandwales.xlsx"
)
SOC_PAGE = (
    "https://www.ons.gov.uk/methodology/classificationsandstandards/standardoccupationalclassificationsoc/"
    "soc2020/soc2020volume1structureanddescriptionsofunitgroups"
)
CAVEATS = [
    "Census Day was 21 March 2021; this is historical workforce structure, not current hiring conditions.",
    "Counts are ONS estimates rounded to the nearest five; shares are published to one decimal place.",
    "LQ and percentage-point differences use published rounded shares, not unrounded underlying counts.",
    "Employed residents are not available candidates; concentration does not establish recruitability or shortage.",
    "The occupation includes all seniority levels and specialisms within the stated SOC unit group.",
    "The district boundary in this release is not an office commuting catchment or a current boundary guarantee.",
    "Small cells are suppressed by ONS; missing values are never replaced with zero.",
    "Census disclosure controls and pandemic conditions affect interpretation; "
    "armed forces are not reliably identified.",
]


@lru_cache(maxsize=4)
def sha256(body: bytes) -> str:
    # Immutable bytes are the cache key: changed evidence always gets a new
    # digest. Discovery can safely reuse one digest across hundreds of rows.
    return hashlib.sha256(body).hexdigest()


def reference() -> dict:
    # The classification and boundary registry is fixed independently of corrected
    # numeric editions. Resolvers do not need to parse active statistical data.
    body = (RESOURCES / "reference.json").read_bytes()
    if sha256(body) != "99be6425455114b39df9a03a56578b68bbabef15cb578044857a32aa99689e3c":
        raise ValueError("Installed source reference failed qualification")
    return json.loads(body)


def worksheet_rows(body: bytes, sheet_name: str, *, start_row: int = 1):
    """Read only literal cells from an official XLSX table; reject formulas."""
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(body)) as book:
        strings = ["".join(x.itertext()) for x in ET.fromstring(book.read("xl/sharedStrings.xml"))]
        sheets = ET.fromstring(book.read("xl/workbook.xml")).find("s:sheets", ns)
        sheet = next(x for x in sheets if x.attrib["name"] == sheet_name)
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = next(x.attrib["Target"] for x in rels if x.attrib["Id"] == rel_id)
        path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        with book.open(path) as stream:
            for _, row in ET.iterparse(stream, events=("end",)):
                if row.tag != "{" + ns["s"] + "}row":
                    continue
                if int(row.attrib["r"]) < start_row:
                    # Some qualified tables have navigation hyperlinks above
                    # their header. Data/formula checks still apply to every
                    # cell from the explicitly selected header onward.
                    row.clear()
                    continue
                cells = {}
                for cell in row:
                    if cell.find("s:f", ns) is not None:
                        raise ValueError("Formula cells are not accepted as publisher observations")
                    value = cell.findtext("s:v", "", ns)
                    if cell.attrib.get("t") == "s":
                        value = strings[int(value)]
                    cells[re.sub(r"\d", "", cell.attrib["r"])] = value.strip()
                yield int(row.attrib["r"]), cells
                row.clear()


def extract_cells(body: bytes) -> list[dict]:
    """Independent reproducible extraction, retaining publisher suppression strings."""
    records = []
    for table in ("1", "3"):
        for row, cells in worksheet_rows(body, table):
            if row == 2 and cells.get("A") != "England and Wales, March 2021":
                raise ValueError("Unexpected Census period or geography")
            if row == 8:
                expected = "Subgroup" if table == "1" else "Local authority district code"
                if cells.get("A") != "SOC2020 Unit Group" or cells.get("C") != expected:
                    raise ValueError("Unexpected Census table schema")
            if row < 9:
                continue
            if not re.fullmatch(r"\d{4}", cells.get("A", "")):
                raise ValueError("Unexpected occupation granularity")
            if table == "1" and cells.get("C") != "Total population":
                continue
            records.append(
                {
                    "geography_id": "K04000001" if table == "1" else cells["C"],
                    "geography_label": "England and Wales" if table == "1" else cells["D"],
                    "soc_code": cells["A"],
                    "soc_label": cells["B"],
                    "count": cells["D" if table == "1" else "E"],
                    "share": cells["E" if table == "1" else "F"],
                    "table": table,
                    "row": str(row),
                    "period": PERIOD,
                    "population": POPULATION,
                }
            )
    if len(records) != 332 * 412:
        raise ValueError("Unexpected Census release dimensions")
    return records


def encode_cells(records: list[dict]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(records[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    # GzipFile keeps the OS header byte stable across Python 3.11-3.13 and OSes;
    # gzip.compress(mtime=0) varies with the linked zlib/Python version.
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", filename="", mtime=0) as stream:
        stream.write(output.getvalue().encode("utf-8"))
    return packed.getvalue()


@lru_cache(maxsize=4)
def read_cells(body: bytes) -> dict:
    result = {}
    for record in csv.DictReader(io.StringIO(gzip.decompress(body).decode("utf-8"))):
        required = {
            "geography_id",
            "geography_label",
            "soc_code",
            "soc_label",
            "count",
            "share",
            "table",
            "row",
            "period",
            "population",
        }
        if set(record) != required or any(value is None for value in record.values()):
            raise ValueError("Unexpected source cell schema")
        key = (record["geography_id"], record["soc_code"])
        if key in result:
            raise ValueError("Duplicate geography/occupation observation")
        result[key] = record
    return result


def snapshot() -> tuple[bytes, dict]:
    ref = reference()
    body = (RESOURCES / "census2021.csv.gz").read_bytes()
    if sha256(body) != ref["evidence"]["snapshot_sha256"]:
        raise ValueError("Installed Census snapshot failed qualification")
    return body, ref
