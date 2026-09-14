"""Frozen official price and earnings growth; never an updated occupation salary."""

import csv
import io
import json
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ._source import sha256

RESOURCES = Path(__file__).parent / "resources"
REFERENCE_HASH = "c59afd029675aeca3a5844a1dabe0d9e2c9e18f284c3805683286801179f7bc8"
VERSION = "ons_prices_earnings_august2026"
SERIES = {
    "l55o": ("CPIH ANNUAL RATE 00: ALL ITEMS 2015=100", "CPIH inflation", "MM23", "2026 JUL", "19-08-2026", "3.1"),
    "d7g7": ("CPI ANNUAL RATE 00: ALL ITEMS 2015=100", "CPI inflation", "MM23", "2026 JUL", "19-08-2026", "2.9"),
    "kai9": (
        "AWE: Whole Economy Year on Year Three Month Average Growth (%): Seasonally Adjusted Regular Pay Excluding Arrears",
        "Average regular earnings growth",
        "LMS",
        "2026 JUN",
        "18-08-2026",
        "3.5",
    ),
    "kac3": (
        "AWE: Whole Economy Year on Year Three Month Average Growth (%): Seasonally Adjusted Total Pay Excluding Arrears",
        "Average total earnings growth",
        "LMS",
        "2026 JUN",
        "18-08-2026",
        "4.1",
    ),
}
CAVEATS = [
    "Inflation describes UK consumer prices, not the costs experienced by a particular household or a Sheffield cost-of-living estimate. CPIH includes owner occupiers' housing costs and Council Tax; CPI excludes these.",
    "Average weekly earnings describe gross earnings per employee across Great Britain, not an occupation, Sheffield or Northern Ireland. Regular pay excludes bonuses; total pay includes them. Both headline series exclude pay-award arrears and are seasonally adjusted, in nominal terms.",
    "Average earnings growth is not the average individual pay award: workforce composition, hours, overtime and payment timing can change the average. The latest earnings month is provisional and these sample estimates are subject to revision; the selected CSV series do not publish a confidence interval for these observations.",
    "Inflation is a twelve-month rate to July; earnings growth compares April-June with the same three months a year earlier. Do not subtract these mismatched windows to estimate real pay growth, or add annual rates across months.",
    "These observations do not measure growth since the ASHE reference date and do not update its salary figures. No inflation-adjusted salary, forecast, recommended increase or individual purchasing-power estimate is calculated.",
]


def resolve_scope():
    return {
        "version": VERSION,
        "prices": "UK all-items CPIH and CPI, twelve months to July 2026",
        "earnings": "Great Britain whole-economy average weekly earnings, April-June 2026 versus April-June 2025; regular and total, nominal and seasonally adjusted, excluding arrears",
    }


def extract(body, code):
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
    title, _, dataset, period, release, qualified_value = SERIES[code]
    if len(rows) != (646 if dataset == "MM23" else 312) or any(len(r) != 2 for r in rows):
        raise ValueError("Incomplete economic source response")
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError("Duplicate economic source period or metadata")
    metadata = dict(rows[:8])
    if metadata != {
        "Title": title,
        "CDID": code.upper(),
        "Source dataset ID": dataset,
        "PreUnit": "",
        "Unit": "%",
        "Release date": release,
        "Next release": "16 September 2026" if dataset == "MM23" else "15 September 2026",
        "Important notes": "",
    }:
        raise ValueError("Economic series definition or release changed")
    selected = [(i + 1, r) for i, r in enumerate(rows) if r[0] == period]
    if len(selected) != 1 or rows[-1][0] != period:
        raise ValueError("Qualified economic reference period missing or changed")
    line, row = selected[0]
    try:
        value = Decimal(row[1])
    except InvalidOperation:
        raise ValueError("Economic source value missing") from None
    if not value.is_finite() or row[1] != qualified_value:
        raise ValueError("Economic source observation not qualified")
    return {"line": line, "metadata": metadata, "raw": {"period": row[0], "value": row[1]}}


def snapshot():
    raw = (RESOURCES / "economic-reference.json").read_bytes()
    if sha256(raw) != REFERENCE_HASH:
        raise ValueError("Economic reference is not qualified")
    ref = json.loads(raw)
    body = (RESOURCES / "economic-sources.zip").read_bytes()
    if ref["version"] != VERSION or sha256(body) != ref["archive_sha256"]:
        raise ValueError("Economic source archive differs")
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        if sorted(archive.namelist()) != sorted(c + ".csv" for c in SERIES):
            raise ValueError("Unexpected economic source members")
        inputs = {c: archive.read(c + ".csv") for c in SERIES}
    if any(sha256(inputs[c]) != ref["sources"][c]["sha256"] for c in SERIES):
        raise ValueError("Economic original response differs")
    return {c: extract(inputs[c], c) for c in SERIES}, ref


def collect(scope):
    if scope != resolve_scope():
        raise ValueError("Accepted national economic context changed")
    records, ref = snapshot()
    facts, rows = [], []
    for code, record in records.items():
        title, label, dataset, _, release, _ = SERIES[code]
        inflation = dataset == "MM23"
        period = "12 months to July 2026" if inflation else "April-June 2026 vs April-June 2025"
        geography = "United Kingdom" if inflation else "Great Britain"
        basis = (
            "Includes owner occupiers' housing costs and Council Tax"
            if code == "l55o"
            else "Excludes owner occupiers' housing costs and Council Tax"
            if code == "d7g7"
            else "Excludes bonuses and pay-award arrears; seasonally adjusted"
            if code == "kai9"
            else "Includes bonuses, excludes pay-award arrears; seasonally adjusted"
        )
        source = ref["sources"][code]
        value = record["raw"]["value"]
        fact = {
            "id": "economic." + code,
            "label": label,
            "value": value,
            "unit": "percent_year_on_year",
            "display": f"{label}: {value}%; {geography}; {period}. {basis}.",
            "period": period,
            "population": "All-items consumer prices, UK"
            if inflation
            else "Whole-economy gross average weekly earnings per employee, Great Britain; not an individual pay award or occupation pay growth",
            "quality": {
                "release": release,
                "method": "consumer price index" if inflation else "business survey earnings estimate",
                "revision": "Frozen release; latest AWE month provisional and seasonally adjusted estimates revisable",
                "confidence_interval": "not published in selected series",
                "seasonally_adjusted": not inflation,
            },
            "source_cells": [
                {
                    "source_url": source["url"],
                    "source_page": source["page"],
                    "response_sha256": source["sha256"],
                    "source_line": record["line"],
                    "dataset": dataset,
                    "series": code.upper(),
                    "metadata": record["metadata"],
                    "raw": record["raw"],
                }
            ],
            "source_geography": {"label": geography},
            "calculation": "publisher growth rate; no salary uplift or real-pay calculation",
        }
        facts.append(fact)
        rows.append({"label": label, "display": value + "%", "geography": geography, "period": period, "basis": basis})
    return {
        "scope": scope,
        "facts": facts,
        "rows": rows,
        "gaps": [],
        "caveats": CAVEATS,
        "source": {
            "version": VERSION,
            "licence": ref["licence"],
            "source_pages": [v["page"] for v in ref["sources"].values()],
        },
        "status": "supported",
    }
