"""Separately scoped ASHE paid hours; never paired with median annual earnings."""

import gzip
import io
import json
import re
import zipfile

from . import pay
from ._pay_source import PATTERN_SHEETS, number_formats, precision
from ._source import sha256, worksheet_rows
from .identities import reference

RESOURCES = pay.RESOURCES
PACK_HASH = "4aab97e467ece285cbbc6cfa9250e435a111cd129c8760b9fd7480e1235d6ca9"
VERSION = "ashe_paid_hours_2025_provisional_corrected_2025-12-19"
MEASURES = {
    "basic": ("10", "Basic paid hours"),
    "total": ("9", "Total paid hours"),
    "overtime": ("11", "Paid overtime hours"),
}
STATISTICS = {"median": "D", "mean": "F"}
PERIOD = "Pay period including 30 April 2025; weekly paid hours"
POPULATION = "UK employee jobs on adult rates with pay unaffected by absence; all sexes"
CAVEATS = [
    "Pay and hours are separate benchmarks. The hours shown are not necessarily those worked by people earning the median annual pay. Annual earnings cover the preceding tax year and have different eligibility rules; hours refer to the April survey pay period.",
    "These are paid hours, not all hours actually worked; unpaid overtime is not captured. The same accepted whole occupation and working pattern apply, with UK workplace coverage rather than the selected district.",
    "Overtime medians exclude zero responses; overtime means include them. Basic and total medians include eligible jobs. Do not add or subtract medians to derive overtime, or divide annual earnings by these hours to invent hourly pay.",
    "Hours estimates retain their own matching coefficient of variation (CV). Missing, suppressed and nil-or-negligible observations stay gaps. Hours are not a contractual-hours recommendation or an assessment of minimum-wage compliance.",
]


def option(occupation, pattern):
    scope = pay.option(occupation, pattern)
    return {k: v for k, v in scope.items() if k not in ("measure", "source_version")} | {
        "source_version": VERSION,
        "measures": list(MEASURES),
        "statistics": list(STATISTICS),
    }


def extract(body):
    records = {}
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        for measure, (number, label) in MEASURES.items():
            members = []
            for suffix in ("a", "b"):
                choices = [n for n in archive.namelist() if f"14.{number}{suffix} " in n and "SOC20 (4)" in n]
                if len(choices) != 1:
                    raise ValueError("Hours workbook identity differs")
                members.append(choices[0])
            for pattern, sheet in PATTERN_SHEETS.items():
                books = [archive.read(n) for n in members]
                estimates, cvs = [dict(worksheet_rows(b, sheet)) for b in books]
                formats = [number_formats(b, sheet) for b in books]
                if set(estimates) != set(cvs):
                    raise ValueError("Hours estimate and CV rows differ")
                for rows in (estimates, cvs):
                    title = rows[1]["A"]
                    if (
                        f"14.{number}" not in title
                        or "United Kingdom, 2025" not in title
                        or "Paid hours worked" not in title
                    ):
                        raise ValueError("Hours release title differs")
                    if any(rows[5].get(c) != h for c, h in {"B": "Code", "D": "Median", "F": "Mean"}.items()):
                        raise ValueError("Hours column headings differ")
                    notes = " ".join(r.get("A", "") for i, r in rows.items() if i > 558)
                    if (
                        "Employees on adult rates whose pay for the survey pay-period was not affected by absence"
                        not in notes
                    ):
                        raise ValueError("Hours eligibility changed")
                    if (
                        measure == "overtime"
                        and "Estimates of the median and percentiles exclude zero responses, whereas estimates of the mean include zero responses."
                        not in notes
                    ):
                        raise ValueError("Overtime population definition changed")
                for row, cells in estimates.items():
                    code = cells.get("B", "")
                    if not re.fullmatch(r"[0-9]{4}", code):
                        continue
                    if cvs[row].get("B") != code or cvs[row].get("A") != cells["A"]:
                        raise ValueError("Hours and CV identify different jobs")
                    key = "/".join((code, pattern, measure))
                    if key in records:
                        raise ValueError("Duplicate hours observation")
                    values = {}
                    for statistic, column in STATISTICS.items():
                        raw, raw_cv = cells.get(column, ""), cvs[row].get(column, "")
                        for value, fmt in zip((raw, raw_cv), formats, strict=True):
                            if value not in pay.MISSING and precision(fmt.get(f"{column}{row}", "General")) != 1:
                                raise ValueError("Hours display precision differs")
                        values[statistic] = {"raw_value": raw, "raw_cv": raw_cv, "value_precision": 1, "column": column}
                    records[key] = {
                        "code": code,
                        "occupation_label": cells["A"],
                        "working_pattern": pattern,
                        "measure": measure,
                        "sheet": sheet,
                        "row": row,
                        "estimate_member": members[0],
                        "cv_member": members[1],
                        "values": values,
                    }
    if len(records) != 3708 or {r["code"] for r in records.values()} != set(reference()["occupations"]):
        raise ValueError("Hours occupation coverage differs")
    if any(r["occupation_label"] != reference()["pay_occupations"][r["code"]] for r in records.values()):
        raise ValueError("Hours source occupation labels differ")
    return records


def snapshot():
    body = (RESOURCES / "hours.json.gz").read_bytes()
    if sha256(body) != PACK_HASH:
        raise ValueError("Hours evidence is not qualified")
    pack = json.loads(gzip.decompress(body))
    if pack["version"] != VERSION or pack["schema_version"] != 1:
        raise ValueError("Hours edition differs")
    return pack["records"]


def collect(scope):
    if scope != option(scope["occupation"], scope["working_pattern"]):
        raise ValueError("Accepted hours scope changed")
    records = snapshot()
    # Use the same pinned original ASHE archive identity, without changing earnings.
    ref_bytes = (RESOURCES / "pay-reference.json").read_bytes()
    if sha256(ref_bytes) != pay.REFERENCE_HASH:
        raise ValueError("ASHE source reference changed")
    ref = json.loads(ref_bytes)
    facts, gaps, rows = [], [], []
    for measure, (_, label) in MEASURES.items():
        r = records["/".join((scope["occupation"]["code"], scope["working_pattern"], measure))]
        displays = {}
        for stat in STATISTICS:
            pair = r["values"][stat]
            value, cv, quality = pay.cell_quality(pair)
            if value is None:
                gaps.append(label + " (" + stat + "): " + quality + ".")
                displays[stat] = "Unavailable"
                continue
            inclusion = (
                "Excludes zero overtime responses"
                if measure == "overtime" and stat == "median"
                else "Includes zero overtime responses"
                if measure == "overtime"
                else "Eligible employee jobs"
            )
            title = label + " — " + stat
            cells = [
                {
                    "table": "14",
                    "row": str(r["row"]),
                    "column": pair["column"],
                    "member": r[member],
                    "sheet": r["sheet"],
                    "raw": pair[raw],
                    "soc_code": r["code"],
                    "soc_label": r["occupation_label"],
                    "source_url": ref["source"]["source_url"],
                    "archive_sha256": ref["source"]["sha256"],
                }
                for member, raw in (("estimate_member", "raw_value"), ("cv_member", "raw_cv"))
            ]
            facts.append(
                {
                    "id": f"hours.{measure}_{stat}",
                    "label": title,
                    "value": str(value),
                    "unit": "hours/week",
                    "period": PERIOD,
                    "population": POPULATION + "; " + pay.PATTERNS[scope["working_pattern"]] + "; " + inclusion,
                    "quality": {"cv_percent": str(cv), "label": quality, "release_status": "provisional"},
                    "display": f"{title}: {value} hours a week; United Kingdom, {r['occupation_label']}, {pay.PATTERNS[scope['working_pattern']]}. {PERIOD}; {inclusion}; CV {cv}% ({quality}).",
                    "source_cells": cells,
                    "calculation": "Publisher observation; no pairing with earnings or conversion",
                }
            )
            displays[stat] = str(value)
        rows.append({"label": label, **displays})
    return {
        "scope": scope,
        "facts": facts,
        "rows": rows,
        "gaps": gaps,
        "caveats": CAVEATS,
        "source": ref,
        "period": PERIOD,
        "population": POPULATION,
        "status": "supported" if facts else "evidence_gap",
    }
