"""Frozen official UK occupation earnings, never an inferred district salary."""

import gzip
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ._pay_source import PAY_VERSION, pack_key
from ._source import sha256
from .identities import reference

RESOURCES = Path(__file__).parent / "resources"
REFERENCE_HASH = "a1a420c8b1d2c2493a38b6e51a31360ec5526cebb1f19237b1ea62a89f047010"
PATTERNS = {"all": "all working patterns", "full_time": "full-time", "part_time": "part-time"}
MEASURES = {"annual_gross": "annual gross earnings", "hourly_excluding_overtime": "hourly earnings excluding overtime"}
QUANTILES = {"median": "Median", "lower_quartile": "25th percentile", "upper_quartile": "75th percentile"}
MISSING = {
    "": "Missing",
    "x": "Suppressed",
    ".": "Unavailable",
    "..": "Unavailable",
    "-": "Nil or negligible, not an exact zero",
}
CAVEATS = [
    "UK-wide employee-job earnings, not local salary offers or self-employed earnings.",
    "Whole occupation and all sexes; no measured specialism or seniority split.",
    "Percentiles describe pay dispersion; CV describes sampling precision. Neither is a recommended offer or a confidence interval.",
    "Full-time means more than thirty paid hours weekly, or at least twenty-five for teaching professions.",
    "2025 provisional, corrected December 2025; a saved snapshot, not a live salary feed.",
]


def snapshot():
    raw = (RESOURCES / "pay-reference.json").read_bytes()
    if sha256(raw) != REFERENCE_HASH:
        raise ValueError("Installed pay reference failed qualification.")
    ref = json.loads(raw)
    body = (RESOURCES / "pay.json.gz").read_bytes()
    if sha256(body) != ref["snapshot_sha256"]:
        raise ValueError("Installed pay evidence failed qualification.")
    pack = json.loads(gzip.decompress(body))
    if pack["version"] != PAY_VERSION or pack["schema_version"] != 1:
        raise ValueError("Pay edition mismatch.")
    return pack["records"], ref


def option(occupation, pattern="full_time", measure="annual_gross"):
    if occupation != reference()["occupations"].get(occupation.get("code")):
        raise ValueError("Pay needs the qualified SOC2020 occupation.")
    if pattern not in PATTERNS or measure not in MEASURES:
        raise ValueError("Choose a supported working pattern and earnings measure.")
    return {
        "source_occupation_label": reference()["pay_occupations"][occupation["code"]],
        "geography_id": "K02000001",
        "geography_label": "United Kingdom",
        "geography_basis": "workplace",
        "occupation": occupation,
        "working_pattern": pattern,
        "measure": measure,
        "source_version": PAY_VERSION,
    }


def cell_quality(pair):
    raw, raw_cv = pair["raw_value"], pair["raw_cv"]
    if raw in MISSING or raw_cv in MISSING:
        return None, None, MISSING.get(raw, "Matching CV is " + MISSING.get(raw_cv, "missing").lower())
    try:
        value, cv = Decimal(raw), Decimal(raw_cv)
    except InvalidOperation as exc:
        raise ValueError("Unexpected pay observation or quality marker.") from exc
    if not value.is_finite() or not cv.is_finite() or value < 0 or cv < 0:
        raise ValueError("Invalid pay estimate or CV.")
    shown = value.quantize(Decimal(1).scaleb(-pair["value_precision"]))
    shown_cv = cv.quantize(Decimal("0.1"))
    if abs(shown - value) > Decimal("0.00000001") or abs(shown_cv - cv) > Decimal("0.00000001"):
        raise ValueError("Pay precision differs materially from the source display.")
    if shown_cv > 20:
        return None, None, "CV exceeds the qualified publication limit"
    return shown, shown_cv, "precise" if shown_cv <= 5 else "reasonably precise" if shown_cv <= 10 else "acceptable"


def collect(scope):
    if scope != option(scope["occupation"], scope["working_pattern"], scope["measure"]):
        raise ValueError("Pay scope differs from the qualified option.")
    records, ref = snapshot()
    role = scope["occupation"]
    row = records.get(pack_key("uk_occupation", "K02000001", role["code"], scope["working_pattern"], scope["measure"]))
    annual = scope["measure"] == "annual_gross"
    period = "Tax year ending 5 April 2025" if annual else "Pay period including 30 April 2025"
    population = (
        "Employee jobs on adult rates, in the same job for more than a year; includes pay affected by absence"
        if annual
        else "Employee jobs on adult rates with pay unaffected by absence"
    )
    facts, gaps = [], []
    if row and (
        row["occupation_label"] != scope["source_occupation_label"]
        or row["occupation_code"] != role["code"]
        or row["occupation_version"] != "SOC2020"
        or row["geography_id"] != "K02000001"
        or row["table"] != 14
        or row["measure"] != scope["measure"]
        or row["working_pattern"] != scope["working_pattern"]
    ):
        raise ValueError("Pay row does not identify the accepted population.")
    for key, label in QUANTILES.items():
        value, cv, quality = cell_quality(row["values"][key]) if row else (None, None, "No published row")
        if value is None:
            gaps.append(label + " earnings: " + quality + ".")
            continue
        unit = "GBP/year" if annual else "GBP/hour"
        formatted = f"GBP {value:,.0f} per year" if annual else f"GBP {value:,.2f} per hour"
        pair = row["values"][key]
        cells = [
            {
                "table": "14",
                "row": str(row["row"]),
                "column": pair["column"],
                "member": row[member],
                "sheet": row["sheet"],
                "raw": pair[raw_key],
                "geography_label": row["geography_label"],
                "soc_code": row["occupation_code"],
                "soc_label": row["occupation_label"],
                "source_url": ref["source"]["source_url"],
                "archive_sha256": ref["source"]["sha256"],
            }
            for member, raw_key in [("estimate_member", "raw_value"), ("cv_member", "raw_cv")]
        ]
        facts.append(
            {
                "id": "pay." + key,
                "value": str(value),
                "unit": unit,
                "period": period,
                "population": population,
                "quality": {"cv_percent": str(cv), "label": quality, "release_status": "provisional"},
                "display": f"{label} {MEASURES[scope['measure']]}: {formatted}; United Kingdom, {row['occupation_label']}, {PATTERNS[scope['working_pattern']]} employee jobs. {period}; CV {cv}% ({quality}); 2025 provisional.",
                "source_cells": cells,
                "calculation": "Publisher observation; no geographic or occupation adjustment",
            }
        )
    return {
        "scope": scope,
        "facts": facts,
        "gaps": gaps,
        "caveats": [*CAVEATS, population + "."],
        "source": ref,
        "status": "supported" if facts else "evidence_gap",
        "period": period,
        "population": population,
    }
