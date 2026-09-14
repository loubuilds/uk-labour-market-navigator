"""Qualified official new-advert evidence, with its own accepted boundary and period."""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

from ._demand_source import ADVERT_RELEASE, ADVERT_VERSION, CAVEATS
from ._source import sha256
from .identities import reference as identity_reference

RESOURCES = Path(__file__).parent / "resources"
REFERENCE_HASH = "6eff6b31e7d0c9ee0d93cdf063b958a2385d2872b3e318e03b505ee8dd05dc80"


def reference():
    raw = (RESOURCES / "advertising-reference.json").read_bytes()
    if sha256(raw) != REFERENCE_HASH:
        raise ValueError("Installed advertising reference failed qualification.")
    ref = json.loads(raw)
    return ref


def snapshot():
    ref = reference()
    body = (RESOURCES / "advertising.json.gz").read_bytes()
    if sha256(body) != ref["snapshot_sha256"]:
        raise ValueError("Installed advertising evidence failed qualification.")
    pack = json.loads(gzip.decompress(body))
    if pack["schema_version"] != 1 or pack["version"] != ADVERT_RELEASE or ref["version"] != ADVERT_RELEASE:
        raise ValueError("Advertising edition mismatch.")
    return pack["records"], ref


def resolve_scope(base):
    identity = identity_reference()
    ref = {"places": identity["advertising_places"], "occupations": identity["advertising_occupations"]}
    role = base["occupation"]
    if role != identity["occupations"].get(role["code"]) or role["code"] not in ref["occupations"]:
        raise ValueError("No qualified SOC2020 advertising identity.")
    # Resolve candidate source-specific identities BEFORE asking for acceptance.
    # Equal codes do not change the Census boundary into the advert boundary.
    places = [
        ref["places"].get(
            p["id"], {"id": p["id"], "label": p["label"], "version": ADVERT_VERSION, "coverage": "not_published"}
        )
        for p in base["places"]
    ]
    return {
        "places": places,
        "occupation": {"code": role["code"], "label": ref["occupations"][role["code"]], "version": "SOC2020"},
        "source_version": ADVERT_RELEASE,
        "period": "2026Q2",
    }


def collect(scope, base):
    if scope != resolve_scope(base):
        raise ValueError("Advertising selections differ from their source-specific scope.")
    records, ref = snapshot()
    facts, rows, gaps = [], [], []
    role = scope["occupation"]
    for place in scope["places"]:
        key = place["id"] + "/" + role["code"]
        record = records.get(key)
        if place.get("coverage") == "not_published" or record is None or record["raw"] == "[x]":
            reason = "withheld by ONS" if record and record["raw"] == "[x]" else "not published for this district"
            gaps.append(place["label"] + ": new-advert evidence " + reason + ".")
            continue
        if not re.fullmatch(r"[0-9]+", record["raw"]) or type(record["row"]) is not int or record["row"] < 6:
            raise ValueError("Invalid literal advertising source observation.")
        value = int(record["raw"])
        quality = {
            "statistics_in_development": True,
            "partly_imputed": True,
            "imputed_month": "June 2026",
            "increased_uncertainty_since": "November 2025",
            "growth_claims": "withheld",
            "suppression": "not_suppressed",
        }
        cell = {
            "table": "5",
            "column": "AR",
            "row": str(record["row"]),
            "raw": record["raw"],
            "geography_label": place["label"],
            "geography_id": place["id"],
            "geography_version": ADVERT_VERSION,
            "soc_code": role["code"],
            "soc_label": role["label"],
            "source_url": ref["source_url"],
            "workbook_sha256": ref["workbook_sha256"],
        }
        facts.append(
            {
                "id": place["id"] + ".new_adverts",
                "value": str(value),
                "display": f"{place['label']}: {value:,} new online adverts for {role['label']}, April to June 2026. Partly imputed; increased source uncertainty. Not a count of vacancies.",
                "unit": "new_online_adverts",
                "period": "2026-04-01/2026-06-30",
                "population": "New online adverts captured by Textkernel and classified by ONS; not unique vacancies",
                "quality": quality,
                "source_cells": [cell],
                "calculation": "publisher observation",
            }
        )
        rows.append({"id": place["id"], "place": place["label"], "new_adverts": str(value)})
    if gaps:
        facts, rows = [], []
        gaps.append(
            "The selected-area advertising comparison is withheld. No district or older period was substituted; independently supported workforce evidence can still be shown."
        )
    return {
        "scope": scope,
        "facts": facts,
        "rows": rows,
        "gaps": gaps,
        "caveats": CAVEATS,
        "source": {
            k: ref[k] for k in ("source_page", "source_url", "workbook_sha256", "snapshot_sha256", "version", "licence")
        },
        "status": "supported" if facts else "evidence_gap",
    }
