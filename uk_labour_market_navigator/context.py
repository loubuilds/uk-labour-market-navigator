"""Area-wide evidence and like-period benchmarks, without a tightness score."""

from decimal import Decimal, InvalidOperation

from .context_source import BOUNDARY, SOURCES, SURVEY_PERIOD, UK, resolve_scope, snapshot

LABELS = {
    "claimant_rate": "Claimant proportion",
    "claimant_previous": "Previous claimant proportion",
    "claimant_change": "Claimant proportion: year-on-year change",
    "employment_rate": "Employment rate (ages 16-64)",
    "inactivity_rate": "Economic inactivity rate (ages 16-64)",
    "unemployment_rate": "Unemployment rate (economically active ages 16+)",
}
POPULATIONS = {
    "claimant_rate": "People aged 16+ claiming JSA or in the Universal Credit searching-for-work group, divided by residents aged 16-64; not the unemployment rate",
    "employment_rate": "Employed residents aged 16-64 as a percentage of all residents aged 16-64",
    "inactivity_rate": "Residents aged 16-64 neither employed nor unemployed, as a percentage of all residents aged 16-64; not a count of available candidates",
    "unemployment_rate": "Unemployed residents aged 16+ as a percentage of economically active residents aged 16+; ILO definition, not a claimant proportion",
}
CAVEATS = [
    "These are area-wide resident indicators, not occupation-specific labour supply or a measure of available candidates.",
    "Claimants are benefit-defined, not everyone unemployed; eligibility and population-denominator revisions can affect the proportion. The series is not seasonally adjusted; compare the same month a year apart.",
    "Survey and model-based figures retain their published approximate 95% confidence margins. Source-flagged unreliable, suppressed or missing values are withheld. Point differences alone do not establish statistical significance.",
    "Local unemployment is model-based; the UK benchmark is a direct APS survey estimate for the same annual window and age/economic-activity definition. Methods differ; neither is a current monthly unemployment measure.",
    "Employment, inactivity and unemployment have different denominators and estimation methods and must not be added together. Inactive residents are not automatically available for work.",
    "Modelled unemployment uses claimant information, so these are not independent confirmations of labour-market tightness.",
    "APS records moved to 2021 output-area processing; this pack shows annual-window levels only, without a survey trend across that transition.",
    "No automatic tight/loose classification, vacancy-to-unemployment ratio, pay recommendation or employer-specific diagnosis is calculated.",
]


class ObservationGap(ValueError):
    pass


def number(record):
    if record is None:
        raise ObservationGap("not published for this source and period")
    raw = record["raw"]
    if raw["OBS_STATUS"] != "A" or raw["OBS_CONF"] != "F":
        raise ObservationGap(raw["OBS_STATUS_NAME"] if raw["OBS_CONF"] == "F" else "not cleared for publication")
    try:
        value = Decimal(raw["OBS_VALUE"])
    except (InvalidOperation, TypeError):
        raise ObservationGap("source value is unavailable") from None
    if not value.is_finite() or value < 0:
        raise ObservationGap("source value is invalid")
    return value


def observation(records, ref, geo, metric, period="2026-03"):
    if metric == "claimant_rate":
        family = "claimants"
        selected = [records[family].get((geo, period, key)) for key in ("2", "1")]
    elif metric == "unemployment_rate" and geo != UK:
        family = "unemployment"
        selected = [records[family].get((geo, period, key)) for key in ("20100", "20701")]
    else:
        family = "aps"
        variable = {"employment_rate": "45", "inactivity_rate": "111", "unemployment_rate": "83"}[metric]
        selected = [records[family].get((geo, period, variable, key)) for key in ("20599", "21003", "21001", "21002")]
    values = [number(r) for r in selected]
    value = values[0]
    if value > 100:
        raise ObservationGap("published proportion is outside its valid range")
    margin = None if metric == "claimant_rate" else values[1]
    if margin is not None and (margin > 100 or margin >= value or margin <= 0):
        raise ObservationGap("confidence margin is missing or too broad for this presentation")
    if family == "aps" and (values[3] <= 0 or values[2] > values[3]):
        raise ObservationGap("survey numerator or denominator is invalid")
    file, dataset, page = SOURCES[family]
    source = ref["sources"][file]
    label = selected[0]["raw"]["GEOGRAPHY_NAME"]
    method = (
        "administrative benefit count"
        if family == "claimants"
        else "model-based local estimate"
        if family == "unemployment"
        else "APS survey estimate"
    )
    metric_id = "claimant_previous" if metric == "claimant_rate" and period == "2025-07" else metric
    unit = "percent"
    period_label = selected[0]["raw"]["DATE_NAME"]
    short = f"{value:.1f}%" + (f" ±{margin:.1f} pp" if margin is not None else "")
    cells = [
        {
            "dataset": dataset,
            "source_url": source["url"],
            "source_page": page,
            "response_sha256": source["sha256"],
            "source_line": r["line"],
            "period_metadata": ref["period_metadata"][family][period],
            "raw": r["raw"],
        }
        for r in selected
    ]
    quality = {
        "method": method,
        "status": "normal_publication_flags",
        "confidence_level": "95% approximate" if margin is not None else "not a sample estimate",
        "confidence_margin_pp": str(margin) if margin is not None else None,
        "seasonally_adjusted": False if family == "claimants" else None,
    }
    display = f"{label}: {LABELS[metric_id]} {short}; {period_label}; {method}."
    if margin is not None:
        display += " The ± figure is the published approximate 95% confidence margin in percentage points."
    population = POPULATIONS[metric]
    if family == "claimants":
        display += " Not the unemployment rate."
    fact = {
        "id": geo + ".context_" + metric_id,
        "label": label + ": " + LABELS[metric_id],
        "value": str(value),
        "unit": unit,
        "display": display,
        "period": period_label,
        "population": population,
        "quality": quality,
        "source_cells": cells,
        "calculation": "publisher observation",
        "source_geography": {"id": geo, "label": label, "version": BOUNDARY if geo != UK else "UK national aggregate"},
    }
    return {
        "id": geo,
        "place": label,
        "value": str(value),
        "margin": str(margin) if margin is not None else None,
        "display": short,
        "fact": fact,
    }


def collect(scope, base):
    if scope != resolve_scope(base):
        raise ValueError("Accepted wider-market scope changed.")
    records, ref = snapshot()
    facts, rows, gaps = [], [], []
    selected = [p["id"] for p in scope["places"]]
    names = {p["id"]: p["label"] for p in scope["places"]} | {UK: "United Kingdom"}
    claimant_current = None
    for metric in ("claimant_rate", "employment_rate", "inactivity_rate", "unemployment_rate"):
        period = "2026-07" if metric == "claimant_rate" else "2026-03"
        values, missing = [], []
        for geo in [*selected, UK]:
            try:
                values.append(observation(records, ref, geo, metric, period))
            except ObservationGap as exc:
                missing.append(names[geo] + ": " + LABELS[metric] + " unavailable (" + str(exc) + ").")
        if missing:
            gaps.extend(missing)
            gaps.append(
                LABELS[metric] + ": the selected-area comparison is withheld; no area or benchmark is substituted."
            )
            continue
        facts.extend(v["fact"] for v in values)
        rows.append(
            {
                "metric": metric,
                "label": LABELS[metric],
                "period": "July 2026" if metric == "claimant_rate" else SURVEY_PERIOD,
                "observations": values[:-1],
                "benchmark": values[-1],
            }
        )
        if metric == "claimant_rate":
            claimant_current = values
    if claimant_current:
        previous, missing = [], []
        for geo in [*selected, UK]:
            try:
                previous.append(observation(records, ref, geo, "claimant_rate", "2025-07"))
            except ObservationGap as exc:
                missing.append(names[geo] + ": previous claimant proportion unavailable (" + str(exc) + ").")
        if missing:
            gaps.extend(missing)
            gaps.append("Year-on-year claimant comparison withheld; current observations remain usable.")
        else:
            changes = []
            facts.extend(v["fact"] for v in previous)
            for current, before in zip(claimant_current, previous, strict=True):
                change = Decimal(current["value"]) - Decimal(before["value"])
                short = "0.0 pp (unchanged)" if change == 0 else f"{change:+.1f} pp"
                fact = {
                    **current["fact"],
                    "id": current["id"] + ".context_claimant_change",
                    "label": current["place"] + ": " + LABELS["claimant_change"],
                    "value": str(change),
                    "unit": "percentage_points",
                    "period": "July 2025 to July 2026",
                    "display": f"{current['place']}: claimant proportion {before['value']}% in July 2025 to {current['value']}% in July 2026; change {short}. Same-month comparison of published non-seasonally-adjusted proportions; not unemployment change.",
                    "source_cells": [*before["fact"]["source_cells"], *current["fact"]["source_cells"]],
                    "calculation": "latest published proportion minus previous same-month published proportion",
                    "inputs": [before["fact"]["id"], current["fact"]["id"]],
                }
                facts.append(fact)
                changes.append(
                    {
                        "id": current["id"],
                        "place": current["place"],
                        "value": str(change),
                        "margin": None,
                        "display": short,
                        "fact": fact,
                    }
                )
            rows.insert(
                1,
                {
                    "metric": "claimant_change",
                    "label": LABELS["claimant_change"],
                    "period": "July 2025 to July 2026",
                    "observations": changes[:-1],
                    "benchmark": changes[-1],
                },
            )
    return {
        "scope": scope,
        "facts": facts,
        "rows": rows,
        "gaps": gaps,
        "caveats": CAVEATS,
        "source": {
            "version": ref["version"],
            "archive_sha256": ref["archive_sha256"],
            "licence": ref["licence"],
            "source_pages": [v[2] for v in SOURCES.values()],
        },
        "status": "partial" if facts and gaps else "supported" if facts else "evidence_gap",
    }
