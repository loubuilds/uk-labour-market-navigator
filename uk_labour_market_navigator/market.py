"""Compose independently scoped evidence; never turn a missing section into a fact."""

from . import demand
from ._source import DATASET, reference
from .evidence import ALIASES, ScopeChoice
from .evidence import collect as collect_workforce
from .identities import reference as identities


def resolve_market(places, role):
    # The occupation registry is common SOC2020; place versions remain per-source.
    ref = identities()
    term = role.strip().casefold()
    code = ALIASES.get(term)
    choices = [
        r for r in ref["occupations"].values() if r["code"] == code or term in (r["code"], r["label"].casefold())
    ]
    if len(choices) != 1:
        raise ScopeChoice("Tell me about the work involved so I can check the occupation. I will not guess a match.")
    occupation = choices[0]
    candidates = ref["places"]
    selected = []
    for name in places:
        term = {"bristol": "bristol, city of", "edinburgh": "city of edinburgh"}.get(
            name.strip().casefold(), name.strip().casefold()
        )
        choices = [
            p
            for p in candidates.values()
            if p["type"] == "local_authority_district" and term in (p["id"].casefold(), p["label"].casefold())
        ]
        if len(choices) != 1:
            raise ScopeChoice(
                "Which district do you mean? I can check workforce and advertising coverage once the place is clear."
            )
        if choices[0] in selected:
            raise ScopeChoice("Choose each district once.")
        selected.append(choices[0])
    if not 1 <= len(selected) <= 3:
        raise ScopeChoice("Choose one to three named districts for this comparison.")
    return {"places": selected, "occupation": occupation, "source_version": "market_scope_v1"}


def collect_plan(plan):
    if plan["schema_version"] in (3, 4, 5):
        return collect_release(plan)
    if plan["schema_version"] == 1:
        return collect_workforce(plan["scope"])
    base = plan["scope"]
    if base != resolve_market([p["id"] for p in base["places"]], base["occupation"]["code"]):
        raise ValueError("Market scope does not match its qualified identities.")
    ref = reference()
    missing = [p for p in base["places"] if p != ref["places"].get(p["id"])]
    workforce = {
        "scope": base,
        "facts": [],
        "rows": [],
        "gaps": [],
        "caveats": [],
        "source": {},
        "status": "not_requested",
    }
    if plan["include_workforce"]:
        if missing:
            workforce.update(
                status="evidence_gap",
                gaps=[
                    {
                        "place": p["label"],
                        "reason": "this Census pack covers England and Wales districts; no other nation or boundary is substituted",
                    }
                    for p in missing
                ],
            )
        else:
            workforce = collect_workforce({**base, "source_version": DATASET})
    advertising = demand.collect(plan["demand_scope"], base)
    gaps = [
        *plan["gaps"],
        *[g["place"] + ": Census occupation evidence unavailable (" + g["reason"] + ")." for g in workforce["gaps"]],
        *advertising["gaps"],
    ]
    return {
        "schema_version": 2,
        "scope": base,
        "census": workforce,
        "demand": advertising,
        "facts": [*workforce["facts"], *advertising["facts"]],
        "gaps": list(dict.fromkeys(gaps)),
        "caveats": [*workforce["caveats"], *advertising["caveats"]],
    }


def collect_release(plan):
    """An unavailable component never supplies facts or blocks independent evidence."""
    from . import pay

    base = plan["scope"]
    if base != resolve_market([p["id"] for p in base["places"]], base["occupation"]["code"]):
        raise ValueError("The accepted occupation or district identity changed.")
    if plan["include_pay"] and plan["pay_scope"] != pay.option(
        base["occupation"], plan["pay_scope"]["working_pattern"], plan["pay_scope"]["measure"]
    ):
        raise ValueError("The accepted pay scope changed.")

    def missing(label, reason, status="evidence_gap"):
        return {
            "status": status,
            "facts": [],
            "rows": [],
            "gaps": [label + ": " + reason] if reason else [],
            "caveats": [],
            "source": {},
            "scope": base,
        }

    def attempt(label, operation):
        try:
            return operation()
        except (ValueError, OSError, KeyError, TypeError, ArithmeticError):
            return missing(
                label,
                "the installed source could not be verified or read. This component supplies no findings; independent checked sections remain usable.",
            )

    def workforce_operation():
        ref = reference()
        absent = [p["label"] for p in base["places"] if p != ref["places"].get(p["id"])]
        if absent:
            return missing(
                "Workforce",
                "Census occupation evidence unavailable for "
                + ", ".join(absent)
                + "; no other nation or boundary is substituted. The selected workforce comparison is withheld.",
            )
        return collect_workforce({**base, "source_version": DATASET})

    def demand_operation():
        if plan["demand_scope"] != demand.resolve_scope(base):
            raise ValueError("The accepted advertising scope changed.")
        return demand.collect(plan["demand_scope"], base)

    census = (
        attempt("Workforce", workforce_operation)
        if plan["include_workforce"]
        else missing("Workforce", "", "not_requested")
    )
    advertising = (
        attempt("Demand", demand_operation) if plan["include_demand"] else missing("Demand", "", "not_requested")
    )
    earnings = missing("Pay", "", "not_requested")
    if plan["include_pay"]:
        earnings = (
            attempt("Pay", lambda: pay.collect(plan["pay_scope"]))
            if plan["pay_accepted"]
            else missing("Pay", "UK-wide earnings scope was not accepted; no pay substitute is shown.", "declined")
        )
    components = [census, advertising, earnings]
    wider = None
    economic = None
    if plan["schema_version"] in (4, 5) and plan["include_context"]:
        from . import context

        wider = attempt("Wider market", lambda: context.collect(plan["context_scope"], base))
        components.append(wider)
        from . import economic as economic_source

        economic = attempt("Prices and pay growth", lambda: economic_source.collect(plan["economic_scope"]))
        components.append(economic)
    paid_hours = None
    if plan["schema_version"] == 5:
        from . import hours

        if plan["hours_scope"] != hours.option(base["occupation"], plan["pay_scope"]["working_pattern"]):
            raise ValueError("Accepted hours scope changed.")
        paid_hours = (
            attempt("Paid hours", lambda: hours.collect(plan["hours_scope"]))
            if plan["pay_accepted"]
            else missing("Paid hours", "", "declined")
        )
        components.append(paid_hours)
    gaps = list(plan["gaps"])
    for component in components:
        gaps.extend(g["place"] + ": " + g["reason"] if isinstance(g, dict) else g for g in component["gaps"])
        gaps.extend(component.get("metric_gaps", []))
    return {
        "schema_version": plan["schema_version"],
        "scope": base,
        **({"context": wider, "economic": economic} if wider is not None else {}),
        **({"hours": paid_hours} if paid_hours is not None else {}),
        "census": census,
        "demand": advertising,
        "pay": earnings,
        "facts": [f for c in components for f in c["facts"]],
        "gaps": list(dict.fromkeys(gaps)),
        "caveats": [x for c in components for x in c["caveats"]],
    }


def answer_gaps(plan, evidence):
    """Keep explicit requirements; separate declined optional scope from missing data."""
    gaps = list(dict.fromkeys([*plan["gaps"], *evidence.get("gaps", [])]))
    component = evidence.get("pay", {})
    if component.get("status") == "declined":
        gaps = [g for g in gaps if g not in component["gaps"] or g in plan["gaps"]]
    return gaps
