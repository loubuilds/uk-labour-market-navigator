"""Bounded drafting aids derived only from collected facts; no hiring diagnosis."""

from decimal import Decimal
from itertools import combinations


def discussion_points(evidence):
    """Compare published values, preserving ties, missing facts and source families.

    These are host drafting inputs, not an extra evidence family or a semantic
    check of the host's prose. Source fact IDs carry every comparison's basis.
    """
    points = []
    facts = {f["id"]: f for f in evidence["facts"]}
    places = evidence["scope"]["places"]
    for metric, description, qualifier in (
        ("count", "residents employed in this occupation", "Census 2021; rounded published counts."),
        (
            "share",
            "share of employed residents in this occupation",
            "Census 2021; rounded published shares, not a hiring-ease measure.",
        ),
        (
            "new_adverts",
            "new online adverts for this occupation",
            "April-June 2026; June partly imputed. This is advertising volume, not competition or a trend.",
        ),
    ):
        for left, right in combinations(places, 2):
            ids = [p["id"] + "." + metric for p in (left, right)]
            if not all(i in facts for i in ids):
                continue
            a, b = (Decimal(facts[i]["value"]) for i in ids)
            relation = "higher" if a > b else "lower" if a < b else "equal"
            points.append(
                {
                    "comparison": f"{left['label']} compared with {right['label']}: {relation} published {description}.",
                    "fact_ids": ids,
                    "qualification": qualifier
                    + " Equal published values are a tie; do not imply statistical significance.",
                }
            )
    # Local occupation share can be compared with its actual England/Wales
    # benchmark even if concentration is unavailable due to a rounded zero.
    for place in places:
        ids = [place["id"] + suffix for suffix in (".share", ".benchmark_share")]
        if not all(i in facts for i in ids):
            continue
        local, benchmark = (Decimal(facts[i]["value"]) for i in ids)
        relation = "above" if local > benchmark else "below" if local < benchmark else "equal to"
        points.append(
            {
                "comparison": f"{place['label']}'s published occupation share is {relation} the England and Wales share.",
                "fact_ids": ids,
                "qualification": "Census 2021 employed residents. This describes relative representation, not candidate availability, employer competition or hiring difficulty.",
            }
        )
    for row in evidence.get("context", {}).get("rows", []):
        if row["metric"] == "claimant_change":
            continue
        benchmark = row["benchmark"]
        for local in row["observations"]:
            a, b = Decimal(local["value"]), Decimal(benchmark["value"])
            relation = "above" if a > b else "below" if a < b else "equal to"
            qualification = "Area-wide, not occupation-specific. No candidate availability, tight/loose classification or pay diagnosis follows."
            if local["margin"] is not None:
                qualification += " Preserve the confidence margins and estimation methods; point differences are not a significance test."
                overlap = abs(a - b) <= Decimal(local["margin"]) + Decimal(benchmark["margin"])
                if overlap:
                    qualification += " The displayed confidence ranges overlap; do not describe a clear difference."
            points.append(
                {
                    "comparison": local["place"]
                    + ": published "
                    + row["label"]
                    + " is "
                    + relation
                    + " the UK benchmark ("
                    + row["period"]
                    + ").",
                    "fact_ids": [local["fact"]["id"], benchmark["fact"]["id"]],
                    "qualification": qualification,
                }
            )
    return points
