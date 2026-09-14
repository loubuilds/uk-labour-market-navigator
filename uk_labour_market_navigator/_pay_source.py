"""Literal ASHE extraction and an offline pack; no estimated taxonomic crosswalks."""

from __future__ import annotations

import gzip
import io
import json
import re
import zipfile
from xml.etree import ElementTree as ET

from ._source import worksheet_rows

PAY_VERSION = "ashe_2025_provisional_corrected_2025-12-19"
QUANTILES = {"median": "D", "lower_quartile": "J", "upper_quartile": "O"}
TABLE_KINDS = {14: "uk_occupation", 3: "regional_occupation", 8: "area_all_occupations"}
PATTERN_SHEETS = {"all": "All", "full_time": "Full-Time", "part_time": "Part-Time"}
MEASURE_TABLES = {"annual_gross": "7", "hourly_excluding_overtime": "6"}


def number_formats(body: bytes, sheet_name: str) -> dict[str, str]:
    """Retain publisher display formats, independently of Excel's stored decimals."""
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(body)) as book:
        styles = ET.fromstring(book.read("xl/styles.xml"))
        formats = {"0": "General", "1": "0", "2": "0.00", "3": "#,##0", "4": "#,##0.00"}
        custom = styles.find("s:numFmts", ns)
        if custom is not None:
            formats.update({x.attrib["numFmtId"]: x.attrib["formatCode"] for x in custom})
        style_formats = [formats.get(x.attrib["numFmtId"], "unsupported") for x in styles.find("s:cellXfs", ns)]
        sheets = ET.fromstring(book.read("xl/workbook.xml")).find("s:sheets", ns)
        sheet = next(x for x in sheets if x.attrib["name"] == sheet_name)
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = next(x.attrib["Target"] for x in rels if x.attrib["Id"] == rel_id)
        path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        return {
            cell.attrib["r"]: style_formats[int(cell.attrib.get("s", "0"))]
            for cell in ET.fromstring(book.read(path)).findall(".//s:c", ns)
        }


def precision(format_code: str) -> int:
    match = re.search(r"[#0][#0,]*(?:\.(0+))?", format_code.split(";")[0])
    if match is None:
        raise ValueError("Unknown publisher numeric format")
    return len(match[1] or "")


def pack_key(kind: str, geo: str, occupation: str, pattern: str, measure: str) -> str:
    return "/".join((kind, geo, occupation, pattern, measure))


def extract_pay(archive_body: bytes, table: int) -> dict:
    records = {}
    with zipfile.ZipFile(io.BytesIO(archive_body)) as archive:
        for measure, number in MEASURE_TABLES.items():
            members = [next(n for n in archive.namelist() if f"{table}.{number}{s} " in n) for s in ("a", "b")]
            if table in (14, 3) and any(f"SOC20 ({4 if table == 14 else 2})" not in n for n in members):
                raise ValueError("Pay source does not declare the qualified SOC2020 granularity")
            for pattern, sheet in PATTERN_SHEETS.items():
                estimates, cv = [dict(worksheet_rows(archive.read(n), sheet)) for n in members]
                estimate_formats, cv_formats = [number_formats(archive.read(n), sheet) for n in members]
                for rows in (estimates, cv):
                    if "2025" not in rows[1]["A"] or "United Kingdom" not in rows[1]["A"]:
                        raise ValueError("Unexpected ASHE release title")
                    if any(rows[5].get(k) != v for k, v in {"B": "Code", "D": "Median", "J": "25", "O": "75"}.items()):
                        raise ValueError("Unexpected ASHE column headings")
                if set(estimates) != set(cv):
                    raise ValueError("Estimate and quality worksheets are misaligned")
                geography, geography_label = "K02000001", "United Kingdom"
                for row, cells in estimates.items():
                    code, label = cells.get("B", ""), cells.get("A", "")
                    if table == 3 and re.fullmatch(r"[EWSNK]\d{8}", code):
                        geography, geography_label = code, label
                        continue
                    selected = (
                        (table == 14 and re.fullmatch(r"\d{4}", code))
                        or (table == 3 and re.fullmatch(r"\d{2}", code))
                        or (table == 8 and re.fullmatch(r"[EWSNK]\d{8}", code))
                    )
                    if not selected:
                        continue
                    if cv[row].get("B") != code or cv[row].get("A") != label:
                        raise ValueError("ASHE estimate and CV identify different populations")
                    if table == 8:
                        geography, geography_label = code, label
                    occupation = "all" if table == 8 else code
                    key = pack_key(TABLE_KINDS[table], geography, occupation, pattern, measure)
                    if key in records:
                        raise ValueError("Duplicate ASHE observation scope")
                    for column in QUANTILES.values():
                        for raw, fmt, digits in (
                            (
                                cells.get(column, ""),
                                estimate_formats.get(f"{column}{row}", "General"),
                                0 if measure == "annual_gross" else 2,
                            ),
                            (cv[row].get(column, ""), cv_formats.get(f"{column}{row}", "General"), 1),
                        ):
                            if raw not in ("", "x", ".", "..", "-") and precision(fmt) != digits:
                                raise ValueError("ASHE numeric precision differs from the qualified display contract")
                    records[key] = {
                        "table": table,
                        "estimate_member": members[0],
                        "cv_member": members[1],
                        "sheet": sheet,
                        "row": row,
                        "source_title": estimates[1]["A"],
                        "geography_id": geography,
                        "geography_label": geography_label,
                        "occupation_code": occupation,
                        "occupation_label": "All occupations" if table == 8 else label,
                        "occupation_version": "not_applicable" if table == 8 else "SOC2020",
                        "working_pattern": pattern,
                        "measure": measure,
                        "values": {
                            q: {
                                "raw_value": cells.get(column, ""),
                                "raw_cv": cv[row].get(column, ""),
                                "column": column,
                                "value_format": estimate_formats.get(f"{column}{row}", "General"),
                                "cv_format": cv_formats.get(f"{column}{row}", "General"),
                                "value_precision": 0 if measure == "annual_gross" else 2,
                            }
                            for q, column in QUANTILES.items()
                        },
                    }
    return records


def encode_pack(value: dict) -> bytes:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", filename="", mtime=0) as stream:
        stream.write(raw)
    return packed.getvalue()
