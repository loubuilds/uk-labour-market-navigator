"""Resumable question -> plan -> evidence -> host synthesis -> checked report."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from .evidence import canonical, resolve
from .market import answer_gaps, collect_plan, resolve_market
from .paths import linked


def unlinked(path: Path):
    path = Path(path)
    if any(linked(p) for p in (path, *path.parents)):
        raise ValueError("Use an unlinked local research path.")
    return path


def read(path: Path):
    return json.loads(unlinked(path).read_text(encoding="utf-8"))


def read_draft(path: Path):
    """Accept a UTF-8 BOM from external editors, without relaxing saved-run reads."""
    return json.loads(unlinked(path).read_text(encoding="utf-8-sig"))


def write_text(path: Path, text: str):
    """Replace one file atomically; never follow a linked target or ancestor."""
    path = unlinked(path)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        unlinked(path)
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write(path: Path, data):
    write_text(path, canonical(data))


def safe_run(run):
    run = unlinked(run)
    if not run.is_dir():
        raise ValueError("Use a local research folder created by this application.")
    identity = read(run / "run-identity.json")
    if (
        not isinstance(identity, dict)
        or set(identity) != {"application", "schema_version", "run_id"}
        or identity["application"] != "uk_labour_market_navigator"
        or type(identity["schema_version"]) is not int
        or identity["schema_version"] != 1
        or identity["run_id"] != run.name
        or not re.fullmatch(r"research-[a-f0-9]{12}", run.name)
    ):
        raise ValueError("This folder is not an identified research run.")
    for name in (
        "plan.json",
        "state.json",
        "evidence.json",
        "synthesis.json",
        "evidence-seal.json",
        "synthesis-context.json",
        "manifest.json",
        "brief.html",
        "brief.md",
    ):
        unlinked(run / name)


def public_text(value: str, limit: int = 1600) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("Use a short general description.")
    patterns = (
        r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|https?://|[A-Z]:[\\/]|/(?:Users|home)/",
        r"\b(?:api[_ -]?key|password|secret|token|access_token)\s*[:=]|bearer\s+\S+",
        r"sk-(?:ant-|proj-)?[A-Za-z0-9_-]{10,}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}",
        r"(?<!\w)(?:\+44\s?|0)[127](?:[\d ()-]){8,13}(?!\d)",
        r"[<>\x00-\x08\x0b\x0c\x0e-\x1f]|!\[|\]\s*\(|(?:javascript|data):|//[A-Za-z]",
    )
    if any(re.search(pattern, value, re.I) for pattern in patterns):
        raise ValueError(
            "Use plain general context without contact details, private paths, credentials or active markup."
        )
    return value.strip()


def check_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("Unexpected research plan.")
    fields = {
        "schema_version",
        "question",
        "purpose",
        "scope",
        "gaps",
        "scope_accepted",
    }
    if plan.get("schema_version") in (2, 3, 4, 5):
        fields |= {"demand_scope", "include_workforce"}
        if type(plan.get("include_workforce")) is not bool:
            raise ValueError("Choose whether workforce context is included.")
    if plan.get("schema_version") in (3, 4, 5):
        fields |= {"requested_role", "include_demand", "include_pay", "pay_scope", "pay_accepted"}
        public_text(plan["requested_role"])
        if any(type(plan[k]) is not bool for k in ("include_demand", "include_pay", "pay_accepted")):
            raise ValueError("Evidence selections and pay acceptance must be explicit.")
        if not plan["include_demand"] and plan["demand_scope"] is not None:
            raise ValueError("Unrequested demand cannot carry a scope.")
        if not plan["include_pay"] and (plan["pay_scope"] is not None or plan["pay_accepted"]):
            raise ValueError("Unrequested pay cannot be accepted.")
    if plan.get("schema_version") == 4:
        fields |= {"include_context", "context_scope", "economic_scope"}
        if (
            plan.get("include_context") is not True
            or not isinstance(plan.get("context_scope"), dict)
            or not isinstance(plan.get("economic_scope"), dict)
        ):
            raise ValueError("Wider-market scope must be explicitly proposed.")
    if plan.get("schema_version") == 5:
        fields |= {"include_hours", "hours_scope", "include_context", "context_scope", "economic_scope"}
        if (
            plan.get("include_hours") is not True
            or not plan["include_pay"]
            or not isinstance(plan.get("hours_scope"), dict)
        ):
            raise ValueError("Paid hours need an explicitly proposed UK occupation scope.")
        if type(plan.get("include_context")) is not bool:
            raise ValueError("Context selection must be explicit.")
        for field in ("context_scope", "economic_scope"):
            if (plan["include_context"] and not isinstance(plan[field], dict)) or (
                not plan["include_context"] and plan[field] is not None
            ):
                raise ValueError("Context scope must match its selection.")
    if set(plan) != fields:
        raise ValueError("Unexpected research plan.")
    if (
        type(plan["schema_version"]) is not int
        or plan["schema_version"] not in (1, 2, 3, 4, 5)
        or type(plan["scope_accepted"]) is not bool
    ):
        raise ValueError("Unsupported research plan.")
    public_text(plan["question"])
    public_text(plan["purpose"])
    if not isinstance(plan["gaps"], list) or len(plan["gaps"]) > 12:
        raise ValueError("Keep a bounded list of unanswered requirements.")
    for gap in plan["gaps"]:
        public_text(gap)


def start(
    question,
    purpose,
    places,
    role,
    gaps,
    runs: Path,
    *,
    include_demand=False,
    include_workforce=True,
    release=False,
    requested_role=None,
    include_pay=False,
    pay_pattern="full_time",
    pay_measure="annual_gross",
    include_context=False,
    include_hours=False,
):
    plan = {
        "schema_version": 1,
        "question": public_text(question),
        "purpose": public_text(purpose),
        "scope": resolve_market(places, role) if include_demand or release else resolve(places, role),
        "gaps": [public_text(g) for g in gaps],
        "scope_accepted": False,
    }
    if include_demand:
        from .demand import resolve_scope

        plan.update(schema_version=2, demand_scope=resolve_scope(plan["scope"]), include_workforce=include_workforce)
    elif not include_workforce and not (release and include_pay):
        raise ValueError("Choose workforce context, demand, or both.")
    if release:
        from . import pay

        requested = public_text(requested_role or role)
        terms = question + " " + requested
        inferred_gaps = []
        # Bounded requirements preservation, not a universal occupation classifier.
        for pattern, gap in [
            (r"\bjava\b", "Java specialism is not measured by these whole-occupation sources."),
            (
                r"\b(senior|junior|principal|graduate|seniority)\b",
                "Seniority is not measured by these whole-occupation sources.",
            ),
            (
                r"\b(radius|commut\w*|miles?|travel.time)\b",
                "Radius or commuting reach is not measured; accepted districts remain separate scope.",
            ),
            (r"\b(available|availability|candidates?)\b", "Current candidate availability is not measured."),
        ]:
            if re.search(pattern, terms, re.I):
                inferred_gaps.append(gap)
        plan.update(
            schema_version=3,
            requested_role=requested,
            include_workforce=include_workforce,
            include_demand=include_demand,
            demand_scope=plan.get("demand_scope"),
            include_pay=include_pay,
            pay_accepted=False,
            pay_scope=pay.option(plan["scope"]["occupation"], pay_pattern, pay_measure) if include_pay else None,
            gaps=list(dict.fromkeys([*plan["gaps"], *inferred_gaps])),
        )
    if include_context:
        if not release:
            raise ValueError("Wider context requires the current research workflow.")
        from .context_source import resolve_scope as context_scope
        from .economic import resolve_scope as economic_scope

        plan.update(
            schema_version=4,
            include_context=True,
            context_scope=context_scope(plan["scope"]),
            economic_scope=economic_scope(),
        )
    if include_hours:
        if not release or not include_pay:
            raise ValueError("Hours accompany an explicitly proposed UK pay investigation.")
        from .hours import option as hours_option

        plan.update(
            schema_version=5,
            include_hours=True,
            hours_scope=hours_option(plan["scope"]["occupation"], pay_pattern),
            include_context=include_context,
            context_scope=plan.get("context_scope"),
            economic_scope=plan.get("economic_scope"),
        )
    check_plan(plan)
    run = runs / ("research-" + uuid4().hex[:12])
    unlinked(run)
    run.mkdir(parents=True, exist_ok=False)
    write(
        run / "run-identity.json",
        {"application": "uk_labour_market_navigator", "schema_version": 1, "run_id": run.name},
    )
    write(run / "plan.json", plan)
    write(run / "state.json", {"stage": "scope_choice"})
    names = ", ".join(p["label"].replace(", City of", "") for p in plan["scope"]["places"])
    label = {"2134": "software-development work", "7211": "call and contact-centre work"}.get(
        plan["scope"]["occupation"]["code"], plan["scope"]["occupation"]["label"]
    )
    message = (
        f"I can start with the size and concentration of {label} in {names}, using Census 2021 district evidence. "
        "This covers employed residents across the whole occupation and all seniority levels, not people currently "
        "available to hire. Does that district-based starting point work for you?"
    )
    if include_demand:
        source_names = ", ".join(p["label"] for p in plan["demand_scope"]["places"])
        message = (
            f"I can explore employer advertising for {label} in {source_names}, using April to June 2026 new-advert figures on April 2023 district boundaries. "
            + (
                "Alongside that, I can check resident workforce context at Census 2021 on its separately published districts; that pack covers England and Wales only. "
                if include_workforce
                else ""
            )
            + "The evidence covers the whole occupation across seniority levels. The advert figures are partly estimated and measure new advertising, not everyone hiring today or people available to hire. Does that starting view fit your question?"
        )
    if release:
        message = (
            f"I can put together a starting view of {label} in {names}, across specialisms and seniority levels.\n\n"
        )
        if not include_workforce and not include_demand:
            message = (
                f"I can show a UK-wide earnings benchmark for {label}, across specialisms and seniority levels.\n\n"
            )
        if plan["gaps"]:
            message += "Still outside this view: " + " ".join(plan["gaps"]) + "\n\n"
        if include_workforce:
            from .evidence import CENSUS_LABELS

            historical_label = CENSUS_LABELS.get(plan["scope"]["occupation"]["code"])
            if historical_label:
                message += (
                    f"The Census source calls this unit {historical_label}; I will retain that historical scope. "
                )
            unavailable = [p["label"] for p in plan["scope"]["places"] if p["id"].startswith(("S", "N"))]
            if unavailable:
                message += (
                    "This Census workforce pack does not cover "
                    + ", ".join(unavailable)
                    + "; the selected workforce comparison will remain unanswered while available evidence continues.\n"
                )
            else:
                message += f"- Workforce: people living in {names} and working in this occupation at Census 2021, using the council areas in that release.\n"
        if include_demand:
            message += "- Advertising: new online adverts in April-June 2026, using the separate April 2023 council boundaries. June is partly estimated.\n"
        if include_pay:
            message += f"- Optional pay: a separate UK-wide benchmark for {pay.PATTERNS[pay_pattern]} {pay.MEASURES[pay_measure]} from ASHE 2025; this covers the whole occupation, not local or specialist salaries.\n"
        if include_hours:
            message += "- Alongside UK pay: separate weekly paid-hours benchmarks for the same occupation and working pattern, April 2025. These are not the hours associated with the median annual earnings.\n"
        if include_pay and plan["pay_scope"]["source_occupation_label"] != plan["scope"]["occupation"]["label"]:
            message += (
                "The ASHE source calls this occupation "
                + plan["pay_scope"]["source_occupation_label"]
                + "; its literal scope is retained. "
            )
        if include_context:
            message += "- Wider market: area-wide claimant proportions for July 2026 and July 2025, plus employment, inactivity and model-based local unemployment for April 2025 to March 2026, on Nomis April 2023 districts. These compare with labelled UK benchmarks; UK unemployment uses a survey estimate. They are not specific to this occupation.\n"
            message += "- Prices and pay growth: UK consumer-price inflation to July 2026 and Great Britain average earnings growth for April-June 2026. These are national context, not an updated salary for this role or a measure of individual pay rises.\n"
        message += "\nDoes that starting view fit your question?"
        if include_pay:
            message += " And would you like the UK pay benchmark included?"
    return {
        "status": "scope_choice",
        "run": str(run.resolve()),
        "proposal": message,
        "gaps": plan["gaps"],
        "next_action": "After acceptance, run collect RUN --accept, adding --accept-pay or --decline-pay when pay is proposed. No questionnaire is needed.",
    }


def gather(run: Path, accepted: bool, pay_accepted=None):
    safe_run(run)
    state = read(run / "state.json")
    if state["stage"] != "scope_choice":
        raise ValueError("This investigation has already advanced. Use status/show, or start a new investigation.")
    plan = read(run / "plan.json")
    check_plan(plan)
    if not accepted:
        return {"status": "scope_choice", "message": "The starting scope still needs your acceptance."}
    if plan["schema_version"] in (3, 4, 5) and plan["include_pay"]:
        if type(pay_accepted) is not bool:
            return {
                "status": "scope_choice",
                "message": "Accept or decline the separately proposed UK pay scope before collection.",
            }
        plan["pay_accepted"] = pay_accepted
    evidence = collect_plan(plan)
    if not evidence["facts"]:
        return {
            "status": "evidence_gap",
            "gaps": evidence["gaps"],
            "message": "Some selected districts have unavailable figures. I can help choose a revised comparison; no place has been omitted automatically.",
        }
    plan["scope_accepted"] = True
    write(run / "plan.json", plan)
    write(run / "evidence.json", evidence)
    write(run / "evidence-seal.json", {name: digest(run / name) for name in ("plan.json", "evidence.json")})
    from .synthesis import discussion_points

    context = {
        "task": "Write a tailored research brief for this person's purpose, using the verified evidence below.",
        "question": plan["question"],
        "purpose": plan["purpose"],
        "requested_role": plan.get("requested_role", plan["scope"]["occupation"]["label"]),
        "gaps": answer_gaps(plan, evidence),
        "declined_components": ["UK pay"] if evidence.get("pay", {}).get("status") == "declined" else [],
        "facts": evidence["facts"],
        "scope": evidence["scope"],
        "caveats": evidence["caveats"],
        "instructions": [
            "Where paid hours are included, keep them separate from earnings. Median pay and median hours need not describe the same jobs, and annual earnings and April hours have different periods and eligibility. Hours are paid hours, not unpaid overtime or contractual hours. Overtime medians exclude zero responses; overtime means include zeros. Never add/subtract medians, pair salary percentiles with hours, divide annual earnings by average hours, or infer a minimum-wage compliance verdict. Use the published hourly pay option for pay comparisons across working weeks, with its own accepted scope.",
            "Where wider-market context is included, consider evidence that strengthens or challenges the person's hypothesis. These rates cover all occupations. Claimant proportions are not unemployment or candidate availability. Local unemployment is model-based, while its UK benchmark is a same-window APS survey estimate; retain that distinction and the confidence margins. Never add employment, unemployment and inactivity rates, interpret inactivity as recruitable supply, or count claimants and modelled unemployment as independent corroboration. A point difference does not establish statistical significance, a tight/loose market or a need for a pay increase. Claimant changes are same-month published proportions, not monthly or unemployment changes. Survey trends across the processing transition are not supplied.",
            "Where prices and earnings growth are included, retain UK price and Great Britain earnings coverage, their different windows, regular versus total pay, nominal basis and arrears exclusion. Average earnings growth is not an individual pay award and reflects composition and hours. Never uplift ASHE, infer cumulative growth since its reference date, subtract mismatched inflation to estimate real pay, or calculate a recommended increase. Use these as context for a human pay discussion, not proof of a local or occupational trend.",
            "Before drafting, offer a short discussion of the evidence's implications for the role and offer, or a brief now. Explain that discussion can tailor next steps to the offer, recruitment messaging and candidate experience. Describe a quick brief as a starting point and explain the value of the practitioner's context and judgement. Do not claim human review or joint authorship that has not occurred. Skip this choice if the person already requested an immediate report or chose a route. If they choose discussion, wait for their response and ask only the next relevant question, not a questionnaire.",
            "Keep user context separate from official evidence. Suggested checks of comparable local adverts, benefits, development, flexibility, employer reviews and social content are external TA investigations, not findings or automated capabilities. Reviews and ratings cannot establish hiring success. Do not save confidential employer information. Material evidence-scope changes need a new accepted investigation.",
            "Write synthesis.json, then run publish RUN --draft synthesis.json. Do not print a technical report to the person.",
            "Use the question and purpose to choose a meaningful opening, interpretation and next questions. Do not merely concatenate facts.",
            "The renderer supplies all accepted facts, dates, population, chart, comparison table and full source ledger. Refer to their fact IDs in each discussion section.",
            "Free prose is agent-authored interpretation, not a source-verified fact. All prose fields must contain no digits, currency signs or percent signs, including dates and numbered titles. The renderer supplies dates and figures. Do not evade this rule by spelling numerical claims out.",
            "Use discussion_points as checked-value comparisons to consider, not a canned report. Select those relevant to this question and cite their fact_ids. Explain the actual direction of a comparison, not just that comparisons are possible.",
            "Each discussion section must cite at least one relevant fact ID from this context. Do not use an empty list or attach unrelated facts to a gap-only section; unanswered requirements already have their own report section.",
            "Before reviewed_by_host=true, check every qualitative claim against its referenced population and period. Concentration alone does not show employers competing or an available developer community. A single quarter cannot establish steady, growing or healthy demand. Census residents are historical, never currently employed residents.",
            "Pay percentiles do not identify seniority or explain the causes of the pay spread. Do not place Senior Java roles in an upper quartile, invent a premium or use employee hourly earnings as contractor rates. A qualitative source uncertainty warning cannot show a difference is small relative to uncertainty or statistically significant.",
            "For missing selected places, that whole family's comparison is withheld. Adding a covered district to a mixed unsupported comparison will not reveal its workforce; offer a separate, explicitly scoped investigation if relevant. Offer implemented investigations or a focused discussion of the role, offer and recruitment messaging; label external TA checks as suggestions. No radius, commuting or live refresh. Respect declined pay without immediately selling it again.",
            "The gaps already include recognised Java, seniority, commuting and availability requirements. Present a repeated requirement once in conversation, retaining distinct requirements. Do not add another wording of an automatically recorded gap.",
            "Interpret cautiously. Employed residents are not available candidates; concentration cannot diagnose shortage. Missing evidence is unknown, never normal.",
            "Preserve the original unanswered requirements. Do not silently answer a wider question.",
            "Where demand is included, synthesize workforce and advertising together for the decision. Keep Census 2021 employed residents separate from April-June 2026 new adverts; never form a demand/supply ratio or competition score from them.",
            "New adverts are not live vacancies or distinct hiring employers. June is partly imputed and source uncertainty is increased; no growth or easy/hard-to-hire verdict follows.",
            "Own the next research step: state what the available evidence changes, what remains unknown, and a useful investigation or discussion follow-up. Tailor suggested TA checks to the actual question rather than a generic coaching checklist.",
        ],
        "discussion_points": discussion_points(evidence),
        "draft_schema": {
            "title": "A title relevant to the question",
            "opening": "Why this evidence helps this discussion",
            "sections": [
                {
                    "heading": "What to take into the conversation",
                    "text": "Your interpretation, without new numerical claims",
                    "fact_ids": [evidence["facts"][0]["id"]],
                }
            ],
            "next_questions": ["A useful question to explore next"],
            "reviewed_by_host": True,
        },
    }
    write(run / "synthesis-context.json", context)
    write(run / "state.json", {"stage": "synthesis"})
    return {
        "status": "awaiting_synthesis",
        "run": str(run.resolve()),
        "context": str((run / "synthesis-context.json").resolve()),
        "message": "The evidence is checked. Bring the brief together for the person's question.",
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_evidence(run):
    safe_run(run)
    seal = read(run / "evidence-seal.json")
    if set(seal) != {"plan.json", "evidence.json"} or any(digest(run / n) != h for n, h in seal.items()):
        raise ValueError("The accepted plan or evidence has changed.")
    plan = read(run / "plan.json")
    check_plan(plan)
    if not plan["scope_accepted"]:
        raise ValueError("The research scope has not been accepted.")
    expected = collect_plan(plan)
    if expected != read(run / "evidence.json") or not expected["facts"]:
        raise ValueError("Saved evidence does not match the qualified source.")
    return plan, expected


def validate_draft(draft, facts):
    if not isinstance(draft, dict) or set(draft) != {
        "title",
        "opening",
        "sections",
        "next_questions",
        "reviewed_by_host",
    }:
        raise ValueError("The synthesis draft must match its documented shape.")
    if draft["reviewed_by_host"] is not True:
        raise ValueError("The host must review its interpretation before publishing the local brief.")
    if not isinstance(draft["sections"], list) or not 1 <= len(draft["sections"]) <= 5:
        raise ValueError("Use one to five focused discussion sections.")
    if not isinstance(draft["next_questions"], list) or not 1 <= len(draft["next_questions"]) <= 3:
        raise ValueError("Offer one to three useful follow-up questions.")
    prose = [("title", draft["title"]), ("opening", draft["opening"])]
    prose.extend((f"next_questions[{i}]", text) for i, text in enumerate(draft["next_questions"]))
    ids = {f["id"] for f in facts}
    for index, section in enumerate(draft["sections"]):
        if not isinstance(section, dict) or set(section) != {"heading", "text", "fact_ids"}:
            raise ValueError("Each discussion section needs its evidence references.")
        refs = section["fact_ids"]
        if not isinstance(refs, list) or not refs or any(not isinstance(i, str) or i not in ids for i in refs):
            raise ValueError(
                f"sections[{index}].fact_ids needs at least one relevant verified fact ID from synthesis-context.json."
            )
        prose.extend((f"sections[{index}].{field}", section[field]) for field in ("heading", "text"))
    for field, text in prose:
        public_text(text)
        if re.search(r"\d|[%\u00a3$\u20ac]", text):
            raise ValueError(
                f"{field}: put figures and dates in referenced facts, not free prose. Remove digits, currency and percent signs; the report supplies the evidence values and periods."
            )
    # This structural check is not a semantic truth or causality classifier.
    # Interpretations are identified explicitly in every report.


def publish(run, draft):
    safe_run(run)
    if read(run / "state.json")["stage"] != "synthesis":
        raise ValueError("Collect evidence first, or start a new investigation to revise a completed brief.")
    plan, evidence = checked_evidence(run)
    validate_draft(draft, evidence["facts"])
    if plan["schema_version"] in (2, 3, 4, 5):
        from .report import render
    else:
        from ._report_v2 import render
    surfaces = render(plan, evidence, draft)
    write(run / "synthesis.json", draft)
    for name, content in surfaces.items():
        write_text(run / name, content)
    names = ["plan.json", "evidence.json", "synthesis.json", *surfaces]
    write(
        run / "manifest.json",
        {
            "version": 15 if plan["schema_version"] in (3, 4, 5) else 3 if plan["schema_version"] == 2 else 2,
            "hashes": {n: digest(run / n) for n in names},
        },
    )
    write(run / "state.json", {"stage": "ready"})
    result = verify(run)
    if result["status"] != "ready":
        raise ValueError("The completed report could not be reverified.")
    return result


def verify(run):
    try:
        safe_run(run)
    except (ValueError, OSError, TypeError, KeyError):
        return {
            "status": "withdrawn",
            "facts_verification": "failed",
            "facts": [],
            "message": "This is not an identified local research run. No files were changed.",
        }
    try:
        stage = read(run / "state.json")["stage"]
        if stage in ("scope_choice", "synthesis"):
            return {
                "status": "incomplete",
                "stage": stage,
                "facts": [],
                "message": "This investigation is unfinished. Continue its current step; no files were changed.",
            }
        if stage != "ready":
            raise ValueError("This report is not ready for reuse.")
        plan, evidence = checked_evidence(run)
        draft = read(run / "synthesis.json")
        validate_draft(draft, evidence["facts"])
        manifest = read(run / "manifest.json")
        version = manifest.get("version")
        if type(version) is not int or version not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15):
            raise ValueError("Unsupported saved report version.")
        if version == 1:
            from ._report_v1 import render
        elif version == 2:
            from ._report_v2 import render
        elif version == 4:
            from ._report_v4 import render
        elif version == 5:
            from ._report_v5 import render
        elif version == 6:
            from ._report_v6 import render
        elif version == 7:
            from ._report_v7 import render
        elif version == 8:
            from ._report_v8 import render
        elif version == 9:
            from ._report_v9 import render
        elif version == 10:
            from ._report_v10 import render
        elif version == 11:
            from ._report_v11 import render
        elif version == 12:
            from ._report_v12 import render
        elif version == 13:
            from ._report_v13 import render
        elif version == 14:
            from ._report_v14 import render
        else:
            from .report import render
        if plan["schema_version"] == 5 and version != 15:
            raise ValueError("Paid-hours evidence requires its recorded renderer.")
        if plan["schema_version"] == 4 and version not in (14, 15):
            raise ValueError("Wider-market evidence requires its recorded current renderer.")
        if (version in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)) != (plan["schema_version"] in (3, 4, 5)) or (
            version == 3
        ) != (plan["schema_version"] == 2):
            raise ValueError("Report format does not match its evidence contract.")
        surfaces = render(plan, evidence, draft)
        names = {"plan.json", "evidence.json", "synthesis.json", *surfaces}
        if set(manifest) != {"version", "hashes"} or set(manifest["hashes"]) != names:
            raise ValueError("Unexpected saved report manifest.")
        if any(digest(run / n) != manifest["hashes"][n] for n in names):
            raise ValueError("A saved report file has changed.")
        if any((run / n).read_text(encoding="utf-8") != text for n, text in surfaces.items()):
            raise ValueError("A readable report differs from the checked evidence and synthesis.")
        gaps = answer_gaps(plan, evidence) if version >= 9 else evidence.get("gaps") or plan["gaps"]
        return {
            "status": "ready",
            "facts_verification": "passed",
            "interpretation": "agent_authored_not_machine_verified",
            "answerability": "partial" if gaps else "accepted_scope_answered",
            "report": str((run / "brief.html").resolve()),
            "markdown": str((run / "brief.md").resolve()),
            "question": plan["question"],
            "next_questions": draft["next_questions"],
            "gaps": gaps,
            "declined_components": ["UK pay"] if evidence.get("pay", {}).get("status") == "declined" else [],
            "checked_facts": [{"id": f["id"], "display": f["display"]} for f in evidence["facts"]],
        }
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return {
            "status": "withdrawn",
            "facts_verification": "failed",
            "facts": [],
            "message": "This saved brief could not be verified. No files were changed. Do not reuse its findings; preserve it for inspection or start a new investigation.",
        }
