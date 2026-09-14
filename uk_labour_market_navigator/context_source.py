"""Pinned original Nomis responses; preserve dimensions, flags and source rows."""

import csv
import io
import json
import zipfile
from pathlib import Path

from ._source import sha256

RESOURCES = Path(__file__).parent / "resources"
REFERENCE_HASH = "815613edde1be9975d48fcf539907a8ab38b64d0892ba565d15c2a5575732aa6"
VERSION = "nomis_context_2026-09-14"
BOUNDARY = "nomis_lad_april2023"
UK = "K02000001"
SURVEY_PERIOD = "Apr 2025-Mar 2026"
APS_VARIABLES = {
    "45": "Employment rate - aged 16-64",
    "83": "Unemployment rate - aged 16+",
    "111": "% who are economically inactive - aged 16-64",
}
APS_MEASURES = {"20599": "Variable", "21001": "Numerator", "21002": "Denominator", "21003": "Confidence"}
SOURCES = {
    "aps": ("aps.csv", "NM_17_5", "https://www.nomisweb.co.uk/datasets/apsnew"),
    "claimants": ("claimants.csv", "NM_162_1", "https://www.nomisweb.co.uk/datasets/ucjsa"),
    "unemployment": ("unemployment.csv", "NM_127_1", "https://www.nomisweb.co.uk/datasets/umb"),
}


def reference():
    body = (RESOURCES / "context-reference.json").read_bytes()
    if sha256(body) != REFERENCE_HASH:
        raise ValueError("The installed wider-market reference is not qualified.")
    result = json.loads(body)
    if result["version"] != VERSION:
        raise ValueError("Wider-market source edition differs.")
    return result


def extract(body, family):
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    expected = {"aps": 4212, "claimants": 1448, "unemployment": 700}[family]
    if len(rows) != expected:
        raise ValueError("Incomplete wider-market source response.")
    records, urns = {}, set()
    for line, row in enumerate(rows, 2):
        if (
            None in row
            or any(v is None for v in row.values())
            or row["RECORD_COUNT"] != str(expected)
            or row["RECORD_OFFSET"] != str(line - 2)
            or row["URN"] in urns
        ):
            raise ValueError("Truncated or duplicate wider-market observation.")
        urns.add(row["URN"])
        geo, period = row["GEOGRAPHY_CODE"], row["DATE"]
        if row["GEOGRAPHY_TYPECODE"] == "424":
            if row["GEOGRAPHY_TYPE"] != "local authorities: district / unitary (as of April 2023)":
                raise ValueError("Unqualified district vintage.")
        elif row["GEOGRAPHY_TYPECODE"] != "499" or geo != UK or row["GEOGRAPHY_NAME"] != "United Kingdom":
            raise ValueError("Unqualified national benchmark.")
        if family == "aps":
            variable, measure = row["VARIABLE"], row["MEASURES"]
            if APS_VARIABLES.get(variable) != row["VARIABLE_NAME"] or APS_MEASURES.get(measure) != row["MEASURES_NAME"]:
                raise ValueError("Survey population or measure changed.")
            key = (geo, period, variable, measure)
        elif family == "claimants":
            if any(
                row[k] != v
                for k, v in {
                    "GENDER": "0",
                    "GENDER_NAME": "Total",
                    "AGE": "0",
                    "AGE_NAME": "All categories: Age 16+",
                    "MEASURES": "20100",
                    "MEASURES_NAME": "Value",
                }.items()
            ):
                raise ValueError("Claimant population changed.")
            if {"1": "Claimant count", "2": "Claimants as a proportion of residents aged 16-64"}.get(
                row["MEASURE"]
            ) != row["MEASURE_NAME"]:
                raise ValueError("Claimant measure changed.")
            key = (geo, period, row["MEASURE"])
        else:
            if (
                row["ITEM"] != "2"
                or row["ITEM_NAME"] != "Unemployment rate (model based)"
                or {"20100": "Value", "20701": "Confidence"}.get(row["MEASURES"]) != row["MEASURES_NAME"]
            ):
                raise ValueError("Modelled unemployment measure changed.")
            key = (geo, period, row["MEASURES"])
        labels = (
            {"2026-07": "July 2026", "2025-07": "July 2025"} if family == "claimants" else {"2026-03": SURVEY_PERIOD}
        )
        if labels.get(period) != row["DATE_NAME"] or key in records:
            raise ValueError("Duplicate observation or unqualified reference period.")
        records[key] = {"line": line, "raw": row}
    expected_keys = (
        {(p, v, m) for p in ("2026-03",) for v in APS_VARIABLES for m in APS_MEASURES}
        if family == "aps"
        else {(p, m) for p in ("2026-07", "2025-07") for m in ("1", "2")}
        if family == "claimants"
        else {("2026-03", m) for m in ("20100", "20701")}
    )
    for geo in {k[0] for k in records}:
        if {k[1:] for k in records if k[0] == geo} != expected_keys:
            raise ValueError("Incomplete source dimensions for a district")
    return records


def snapshot():
    ref = reference()
    body = (RESOURCES / "context-sources.zip").read_bytes()
    if sha256(body) != ref["archive_sha256"]:
        raise ValueError("The installed wider-market sources failed verification.")
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        if set(archive.namelist()) != set(ref["sources"]) or len(archive.namelist()) != len(ref["sources"]):
            raise ValueError("Wider-market source archive has unexpected members.")
        inputs = {name: archive.read(name) for name in ref["sources"]}
    if any(sha256(inputs[n]) != entry["sha256"] for n, entry in ref["sources"].items()):
        raise ValueError("An original source response differs.")
    validate_metadata(inputs, ref)
    records = {family: extract(inputs[file], family) for family, (file, _, _) in SOURCES.items()}
    for family, rows in records.items():
        for record in rows.values():
            raw = record["raw"]
            if raw["GEOGRAPHY_CODE"] != UK:
                place = ref["places"].get(raw["GEOGRAPHY_CODE"])
                if (
                    place is None
                    or place["label"] != raw["GEOGRAPHY_NAME"]
                    or place["boundary"] != raw["GEOGRAPHY_TYPE"]
                ):
                    raise ValueError("Source district identity changed.")
    ref = {
        **ref,
        "period_metadata": {
            family: {
                period: period_record(inputs, family, period)
                for period in (("2026-07", "2025-07") if family == "claimants" else ("2026-03",))
            }
            for family in SOURCES
        },
    }
    return records, ref


def resolve_scope(base):
    ref = reference()
    return {
        "version": VERSION,
        "places": [
            ref["places"].get(
                p["id"], {"id": p["id"], "label": p["label"], "version": BOUNDARY, "coverage": "not_published"}
            )
            for p in base["places"]
        ],
        "benchmark": ref["benchmark"],
        "population": "Area-wide residents; no occupation filter",
        "survey_period": SURVEY_PERIOD,
        "claimant_periods": ["July 2026", "July 2025"],
    }


def codes(body):
    return json.loads(body)["structure"]["codelists"]["codelist"][0]["code"]


def period_record(inputs, family, period):
    filename = {"aps": "aps-periods.json", "claimants": "cc-periods.json", "unemployment": "unemployment-periods.json"}[
        family
    ]
    found = [c for c in codes(inputs[filename]) if c["value"] == period]
    if len(found) != 1:
        raise ValueError("Source period metadata missing or duplicated")
    return found[0]


def validate_metadata(inputs, ref):
    for filename, dataset in (
        ("aps-def.json", "NM_17_5"),
        ("cc-def.json", "NM_162_1"),
        ("unemployment-def.json", "NM_127_1"),
    ):
        d = json.loads(inputs[filename])["structure"]
        if d["header"]["id"] != dataset or d["keyfamilies"]["keyfamily"][0]["id"] != dataset:
            raise ValueError("Dataset identity changed")
    for family, period, label, expected in (
        (
            "aps",
            "2026-03",
            SURVEY_PERIOD,
            {
                "start period": "2025-04-01",
                "end period": "2026-03-01",
                "CurrentRevisionReleased": "2026-07-21 07:00:00",
            },
        ),
        (
            "unemployment",
            "2026-03",
            SURVEY_PERIOD,
            {
                "start period": "apsStartDate",
                "end period": "apsEndDate",
                "CurrentRevisionReleased": "2026-07-21 07:00:00",
            },
        ),
        (
            "claimants",
            "2026-07",
            "July 2026",
            {"taken on": "2026-07-09", "CurrentRevisionReleased": "2026-08-18 07:00:00"},
        ),
        (
            "claimants",
            "2025-07",
            "July 2025",
            {"taken on": "2025-07-10", "CurrentRevisionReleased": "2025-09-16 07:00:00"},
        ),
    ):
        entry = period_record(inputs, family, period)
        annotations = {a["annotationtitle"]: a["annotationtext"] for a in entry["annotations"]["annotation"]}
        if entry["description"]["value"] != label or any(annotations.get(k) != v for k, v in expected.items()):
            raise ValueError("Qualified period metadata changed")
    dimensions = {}
    for entry in codes(inputs["cc-districts.json"]):
        a = {a["annotationtitle"]: a["annotationtext"] for a in entry["annotations"]["annotation"]}
        if a["TypeCode"] != 424 or a["TypeName"] != "local authorities: district / unitary (as of April 2023)":
            raise ValueError("Unqualified geography metadata")
        dimensions[a["GeogCode"]] = entry["description"]["value"]
    if any(dimensions.get(k) != v["label"] for k, v in ref["places"].items()):
        raise ValueError("District metadata and source labels differ")
