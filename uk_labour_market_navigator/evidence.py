"""Small reviewed Census adapter; no network, model or private configuration."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from ._source import CAVEATS, DATASET, PERIOD, POPULATION, read_cells, reference, snapshot

ALIASES = {
    "software developer": "2134",
    "software developers": "2134",
    "software engineer": "2134",
    "software engineers": "2134",
    "programmer": "2134",
    "programmers": "2134",
    "call centre operators": "7211",
    "contact centre operators": "7211",
}


# Literal source titles differ from the separately pinned newer SOC title registry.
# Same SOC2020 unit codes; preserve historical names, never rewrite source rows.
CENSUS_LABELS = {
    "8211": "Large goods vehicle drivers",
    "5223": "Metal working production and maintenance fitters",
    "2122": "Mechanical engineers",
    "2212": "Specialist medical practitioners",
    "6129": "Animal care services occupations n.e.c.",
    "3131": "IT operations technicians",
    "2124": "Electronics engineers",
    "6121": "Pest control officers",
}


class ScopeChoice(ValueError):
    """A missing meaning/scope choice is not a failed research process."""


def resolve(places: list[str], role: str) -> dict:
    ref = reference()
    matched = []
    for name in places:
        term = name.strip().casefold()
        if term == "bristol":
            term = "bristol, city of"
        choices = [
            p
            for p in ref["places"].values()
            if p["type"] == "local_authority_district" and term in (p["label"].casefold(), p["id"].casefold())
        ]
        if len(choices) != 1:
            raise ScopeChoice("Which district do you mean? A district is needed for this first version.")
        if choices[0] in matched:
            raise ScopeChoice("Choose each district once.")
        matched.append(choices[0])
    if not 1 <= len(matched) <= 3:
        raise ScopeChoice("This first version supports one to three named districts.")
    term = role.strip().casefold()
    code = ALIASES.get(term)
    choices = [
        r for r in ref["occupations"].values() if r["code"] == code or term in (r["label"].casefold(), r["code"])
    ]
    if len(choices) != 1:
        raise ScopeChoice(
            "Tell me a little about the work involved so I can check the occupation. I won't guess a match."
        )
    return {"places": matched, "occupation": choices[0], "source_version": DATASET}


def number(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("The source count or share is missing or suppressed.") from exc
    if not value.is_finite() or value < 0:
        raise ValueError("The source count or share is invalid.")
    return value


def collect(scope: dict) -> dict:
    body, ref = snapshot()
    if set(scope) != {"places", "occupation", "source_version"} or scope["source_version"] != DATASET:
        raise ValueError("Unknown source scope.")
    if scope["occupation"] != ref["occupations"].get(scope["occupation"]["code"]):
        raise ValueError("The occupation must match the installed official classification.")
    if not 1 <= len(scope["places"]) <= 3:
        raise ValueError("Choose one to three districts.")
    if len({p["id"] for p in scope["places"]}) != len(scope["places"]):
        raise ValueError("Duplicate districts.")
    for p in scope["places"]:
        if p != ref["places"].get(p["id"]) or p["type"] != "local_authority_district":
            raise ValueError("The district must match the qualified source boundary.")
    cells = read_cells(body)
    role = scope["occupation"]
    facts, rows, gaps = [], [], []
    source_role_label = CENSUS_LABELS.get(role["code"], role["label"])

    def observation(place):
        row = cells.get((place["id"], role["code"]))
        if row is None:
            raise ValueError("There is no source observation.")
        if (
            row["period"] != PERIOD
            or row["population"] != POPULATION
            or row["geography_label"] != place["label"]
            or row["soc_label"].casefold() != CENSUS_LABELS.get(role["code"], role["label"]).casefold()
        ):
            raise ValueError("Source identity or population does not match the accepted scope.")
        count, share = number(row["count"]), number(row["share"])
        if count % 5 or share > 100:
            raise ValueError("The source does not meet its published precision contract.")
        return row, count, share.quantize(Decimal("0.1"))

    benchmark, national_count, national_share = observation(ref["places"]["K04000001"])
    metric_gaps = []
    for place in scope["places"]:
        try:
            cell, count, share = observation(place)
        except ValueError as exc:
            gaps.append({"place": place["label"], "reason": str(exc)})
            continue
        lq = low = high = None
        if national_share:
            lq = (share / national_share).quantize(Decimal("0.01"))
            half = Decimal("0.05")
            low = (max(Decimal(0), share - half) / (national_share + half)).quantize(Decimal("0.01"))
            high = ((share + half) / (national_share - half)).quantize(Decimal("0.01"))
        else:
            metric_gaps.append(
                place["label"]
                + ": concentration unavailable because the published benchmark share rounds to zero; valid workforce count and share are retained."
            )
        key = place["id"]
        entries = [
            (
                "count",
                str(count),
                f"{place['label']}: {count:,.0f} employed residents in {source_role_label}.",
                "persons",
                [cell],
            ),
            (
                "share",
                str(share),
                f"{place['label']}: {share:.1f}% of employed residents were in this occupation.",
                "%",
                [cell],
            ),
            (
                "benchmark_count",
                str(national_count),
                f"England and Wales: {national_count:,.0f} employed residents in this occupation.",
                "persons",
                [benchmark],
            ),
            (
                "benchmark_share",
                str(national_share),
                f"England and Wales: {national_share:.1f}% of employed residents were in this occupation.",
                "%",
                [benchmark],
            ),
        ]
        if lq is not None:
            entries.append(
                (
                    "concentration",
                    str(lq),
                    f"{place['label']}: {lq:.2f} times the England and Wales occupation share. The rounding range is {low:.2f} to {high:.2f}, not a confidence interval.",
                    "ratio",
                    [cell, benchmark],
                )
            )
        for measure, value, display, unit, source_cells in entries:
            facts.append(
                {
                    "id": f"{key}.{measure}",
                    "value": value,
                    "display": display,
                    "unit": unit,
                    "period": PERIOD,
                    "population": POPULATION,
                    "source_cells": source_cells,
                    "calculation": "published local share / published benchmark share"
                    if measure == "concentration"
                    else "publisher observation",
                }
            )
        rows.append(
            {
                "id": key,
                "place": place["label"],
                "count": str(count),
                "share": str(share),
                "benchmark_share": str(national_share),
                "concentration": str(lq) if lq is not None else None,
                "rounding_low": str(low) if low is not None else None,
                "rounding_high": str(high) if high is not None else None,
            }
        )
    # Do not silently omit a selected place and turn a failed comparison into a winner.
    if gaps:
        facts, rows = [], []
    result = {
        "schema_version": 1,
        "scope": scope,
        "facts": facts,
        "rows": rows,
        "gaps": gaps,
        "source": ref["evidence"],
        "caveats": CAVEATS,
        "period": PERIOD,
        "population": POPULATION,
        "comparison_complete": not gaps,
    }
    if source_role_label != role["label"]:
        result["source_occupation_label"] = source_role_label
        metric_gaps.append(
            "Census source occupation label: "
            + source_role_label
            + ". The separate SOC2020 registry labels this unit "
            + role["label"]
            + "; historical observations retain the source title and do not establish identical current duties."
        )
    if metric_gaps:
        result["metric_gaps"] = metric_gaps
    return result


def canonical(data: object) -> str:
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
