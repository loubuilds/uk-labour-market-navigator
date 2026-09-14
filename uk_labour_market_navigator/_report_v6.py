"""Current V0.1 report; legacy renderers are isolated for recorded formats."""

import re
from decimal import Decimal
from html import escape

from ._report_v3 import CSS
from ._report_v3 import render as legacy_render
from .branding import AUTHOR, DESCRIPTION, PRODUCT_NAME
from .evidence import canonical
from .pay import MEASURES


def md_text(value):
    return re.sub(r"([\\`*_{}\[\]()<>#+.!|~])", r"\\\1", str(value))


def chart(rows):
    """Comparable values on a shared zero baseline, with units and period."""
    if len(rows) == 1:
        title = "Share of employed residents in this occupation"
        plots = [
            (rows[0]["place"], Decimal(rows[0]["share"])),
            ("England and Wales", Decimal(rows[0]["benchmark_share"])),
        ]
        suffix = "%"
    else:
        title = "Employed residents in the selected occupation"
        plots = [(row["place"], Decimal(row["count"])) for row in rows]
        suffix = ""
    height = 70 + len(plots) * 70
    maximum = max(value for _, value in plots)
    lines = [
        f"<figure><figcaption>{escape(title)} &middot; Census 2021</figcaption>",
        f'<svg viewBox="0 0 800 {height}" role="img" aria-labelledby="chart-title chart-desc">',
        f'<title id="chart-title">{escape(title)}</title>',
        '<desc id="chart-desc">Published Census 2021 observations on a shared zero baseline. The table gives values, populations and concentration.</desc>',
        '<line x1="245" y1="18" x2="245" y2="' + str(height - 25) + '" stroke="#7c9397"/>',
    ]
    for i, (place, value) in enumerate(plots):
        y = 24 + i * 70
        width = float(value / maximum * 405) if maximum else 0
        display = f"{value:.1f}%" if suffix else f"{value:,.0f}"
        lines.extend(
            [
                f'<text x="0" y="{y + 25}" font-size="16">{escape(place)}</text>',
                f'<rect x="245" y="{y}" width="{width:.3f}" height="36" rx="3" fill="#00766d"/>',
                f'<text x="{255 + width:.3f}" y="{y + 25}" font-size="17">{display}</text>',
            ]
        )
    lines.append(f'<text x="245" y="{height - 3}" font-size="13">0{suffix}</text></svg></figure>')
    return "".join(lines)


def render(plan, evidence, draft):
    if evidence["schema_version"] != 3:
        return legacy_render(plan, evidence, draft)
    html = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta name="referrer" content="no-referrer">',
        "<title>" + escape(draft["title"]) + "</title><style>" + CSS + "</style></head><body><main>",
        '<header><div class="brand">'
        + escape(PRODUCT_NAME)
        + '</div><p class="small">'
        + escape(AUTHOR)
        + " · Independent research software; not an official government service.</p><h1>"
        + escape(draft["title"])
        + '</h1><p class="lead">'
        + escape(draft["opening"])
        + "</p>",
        '<p class="small">Source figures are checked. The explanation and suggested next steps are AI/host interpretation, not machine-proven findings.</p></header>',
    ]
    md = [
        "# " + md_text(draft["title"]),
        md_text(DESCRIPTION),
        md_text(AUTHOR),
        md_text(draft["opening"]),
        "Source figures are checked; AI/host interpretation is not machine-proven.",
    ]

    def section(title, content, markdown):
        html.append('<section class="panel"><h2>' + escape(title) + "</h2>" + content + "</section>")
        md.extend(["## " + title, markdown])

    def bullets(items):
        return "<ul>" + "".join("<li>" + escape(x) + "</li>" for x in items) + "</ul>"

    def table(headings, rows):
        h = (
            '<div class="table"><table><thead><tr>'
            + "".join('<th scope="col">' + escape(c) + "</th>" for c in headings)
            + "</tr></thead><tbody>"
        )
        m = ["| " + " | ".join(headings) + " |", "| " + " | ".join("---" for _ in headings) + " |"]
        for row in rows:
            h += "<tr>" + "".join("<td>" + escape(str(c)) + "</td>" for c in row) + "</tr>"
            m.append("| " + " | ".join(md_text(c) for c in row) + " |")
        return h + "</tbody></table></div>", "\n".join(m)

    def gaps(component):
        return [g["place"] + ": " + g["reason"] if isinstance(g, dict) else g for g in component.get("gaps", [])]

    def source_link(source):
        url = source.get("source_page")
        return (
            '<p class="small">Source: <a href="' + escape(url, quote=True) + '">Office for National Statistics</a></p>'
            if url
            else ""
        )

    role = plan["scope"]["occupation"]["label"]
    names = ", ".join(p["label"] for p in plan["scope"]["places"])
    question = [
        plan["question"],
        "Purpose: " + plan["purpose"],
        "Requested role: " + plan["requested_role"],
        "Measured official occupation: " + role + " (SOC2020 " + plan["scope"]["occupation"]["code"] + ").",
        "Selected districts: " + names + ".",
        "Whole-occupation context includes different specialisms and seniority levels. Specific requirements remain visible below.",
    ]
    section("Your question and the evidence scope", bullets(question), "\n\n".join(md_text(x) for x in question))
    c = evidence["census"]
    workforce_role = c.get("source_occupation_label", role)
    if c.get("status") != "not_requested":
        title = "Resident workforce · Census 2021"
        intro = "People aged sixteen and over who lived in the selected districts and were employed in this occupation at Census 2021. These are historical employed residents, not available candidates."
        intro += " Occupation in this source: " + workforce_role + "."
        h = '<p class="scope">' + escape(intro) + "</p>"
        m = [intro]
        if c["facts"]:
            rows = []
            for row in c["rows"]:
                lq = row["concentration"]
                rows.append(
                    [
                        row["place"],
                        f"{Decimal(row['count']):,.0f}",
                        row["share"] + "%",
                        row["benchmark_share"] + "%",
                        lq + "x" if lq is not None else "Unavailable",
                        row["rounding_low"] + " to " + row["rounding_high"]
                        if lq is not None
                        else "Benchmark rounds to zero",
                    ]
                )
            if len(c["rows"]) == 1:
                row = c["rows"][0]
                h += (
                    '<div class="cards"><div class="card"><span class="value">'
                    + f"{Decimal(row['count']):,.0f}"
                    + "</span><strong>Residents employed as</strong><p>"
                    + escape(workforce_role + " in " + row["place"])
                    + "</p></div>"
                )
                h += (
                    '<div class="card"><span class="value">'
                    + escape(row["share"])
                    + "%</span><strong>Of all employed residents locally</strong><p>work in this occupation.</p></div></div>"
                )
            th, tm = table(
                [
                    "District",
                    "Employed residents",
                    "Local share",
                    "England/Wales share",
                    "Concentration",
                    "Rounding range",
                ],
                rows,
            )
            h += chart(c["rows"]) + th
            m.append(tm)
            note = "Counts are rounded to five and shares to one decimal place. Concentration compares occupation shares, not hiring difficulty. Its rounding range is not a confidence interval. Districts are those tabulated in the May 2023 Census release."
            h += '<p class="small">' + escape(note) + "</p>" + source_link(c["source"])
            m.append(note)
        else:
            h += bullets(gaps(c))
            m.extend(gaps(c))
        section(title, h, "\n\n".join(m))
    d = evidence["demand"]
    if d.get("status") != "not_requested":
        intro = "New online adverts during April to June 2026, assigned to this whole occupation on April 2023 district boundaries. June is partly imputed; source uncertainty has increased since November 2025."
        h = '<p class="scope">' + escape(intro) + "</p>"
        m = [intro]
        if d["facts"]:
            th, tm = table(
                ["District", "New online adverts"],
                [[row["place"], f"{int(row['new_adverts']):,}"] for row in d["rows"]],
            )
            h += th
            m.append(tm)
            note = "This adds a dated signal of employer advertising activity. It does not count live vacancies or distinct competitors. A higher count may reflect a larger market. Dividing it by historical Census residents would not establish recruitment competition or shortage."
            h += "<p>" + escape(note) + "</p>" + source_link(d["source"])
            m.append(note)
        else:
            h += bullets(gaps(d))
            m.extend(gaps(d))
        section("Employer advertising · April–June 2026", h, "\n\n".join(m))
    p = evidence["pay"]
    if p.get("status") != "not_requested":
        h = ""
        m = []
        if p["facts"]:
            intro = "Separately accepted UK-wide earnings benchmark for the whole occupation, shown once for all selected locations. This is actual employee-job earnings, not local or advertised salaries."
            intro += (
                " Measure: "
                + MEASURES[p["scope"]["measure"]]
                + ". Occupation in ASHE: "
                + p["scope"]["source_occupation_label"]
                + "."
            )
            if p["scope"]["source_occupation_label"] != role:
                intro += " This source title differs from the common occupation registry; the source wording and accepted whole-unit scope are retained."
            h = '<p class="scope">' + escape(intro) + "</p>"
            m.append(intro)
            rows = []
            for f in p["facts"]:
                label = {"median": "Median", "lower_quartile": "25th percentile", "upper_quartile": "75th percentile"}[
                    f["id"].split(".")[1]
                ]
                value = (
                    f"GBP {Decimal(f['value']):,.0f}/year"
                    if f["unit"] == "GBP/year"
                    else f"GBP {Decimal(f['value']):,.2f}/hour"
                )
                rows.append([label, value, f["quality"]["cv_percent"] + "%", f["quality"]["label"]])
            th, tm = table(["Earnings measure", "UK benchmark", "CV", "Source precision"], rows)
            h += th
            m.append(tm)
            scope = p["scope"]
            note = (
                p["period"]
                + ". "
                + p["population"]
                + ". Working pattern: "
                + scope["working_pattern"].replace("_", " ")
                + ". All sexes; workplace basis; 2025 provisional, with the December correction retained. Percentiles describe the pay distribution, not a recommended offer range. CV (coefficient of variation) indicates the precision of the estimate. A lower percentage means greater precision."
            )
            h += "<p>" + escape(note) + "</p>" + source_link(p["source"])
            m.append(note)
        h += bullets(gaps(p))
        m.extend(gaps(p))
        section("Official earnings · UK benchmark", h, "\n\n".join(m))
    place_labels = {p["id"]: p["label"] for p in plan["scope"]["places"]}
    measure_labels = {
        "count": "resident count",
        "share": "occupation share",
        "benchmark_count": "England/Wales count",
        "benchmark_share": "England/Wales share",
        "concentration": "concentration",
        "new_adverts": "new adverts",
        "median": "median earnings",
        "lower_quartile": "lower-quartile earnings",
        "upper_quartile": "upper-quartile earnings",
    }

    def reference_label(fact_id):
        area, measure = fact_id.split(".", 1)
        return ("UK" if area == "pay" else place_labels[area]) + ": " + measure_labels[measure]

    h = '<p class="small">The following is AI/host interpretation. Evidence references identify the figures used; they do not prove a qualitative conclusion.</p>'
    m = ["AI/host interpretation; not machine-verified source findings."]
    for s in draft["sections"]:
        h += "<h3>" + escape(s["heading"]) + "</h3><p>" + escape(s["text"]) + '</p><p class="cite">Evidence: '
        labels = []
        for i in s["fact_ids"]:
            label = reference_label(i)
            labels.append(label)
            h += '<a href="#fact-' + escape(i, quote=True) + '">' + escape(label) + "</a> "
        h += "</p>"
        m.extend(
            ["### " + md_text(s["heading"]), md_text(s["text"]), "Evidence: " + "; ".join(md_text(x) for x in labels)]
        )
    section("What to take into the discussion", h, "\n\n".join(m))
    remaining = list(
        dict.fromkeys(
            [
                *evidence["gaps"],
                "These descriptive sources do not establish current candidate availability or an employer-specific reason for hiring difficulty.",
            ]
        )
    )
    section("What remains unanswered", bullets(remaining), "\n".join("- " + md_text(x) for x in remaining))
    section(
        "A useful next step",
        bullets(draft["next_questions"]),
        "\n".join("- " + md_text(x) for x in draft["next_questions"]),
    )
    h = "<p>Open a figure for its meaning, dates and source reference. Technical details are optional.</p>"
    m = []
    for f in evidence["facts"]:
        meaning = f["population"] + ". Period: " + f["period"] + "."
        method = (
            "Calculated from published rounded occupation shares; the range reflects rounding, not sampling confidence."
            if f["id"].endswith(".concentration")
            else "Read from the qualified official source and replayed against the installed snapshot."
        )
        h += (
            '<details id="fact-'
            + escape(f["id"], quote=True)
            + '"><summary>'
            + escape(f["display"])
            + "</summary><p><strong>When and who</strong><br>"
            + escape(meaning)
            + "</p><p><strong>How checked</strong><br>"
            + escape(method)
            + "</p><details><summary>Technical source record</summary><pre>"
            + escape(canonical(f))
            + "</pre></details></details>"
        )
        m.extend(
            [
                "### " + md_text(f["display"]),
                md_text(meaning),
                method,
                "<details><summary>Technical source record</summary>\n\n```json\n" + canonical(f) + "```\n\n</details>",
            ]
        )
    methodology = list(dict.fromkeys(evidence["caveats"]))
    h += "<details><summary>Methodology and source limitations</summary>" + bullets(methodology) + "</details>"
    m.extend(["### Methodology and source limitations", *["- " + md_text(x) for x in methodology]])
    section("Where the numbers come from", h, "\n\n".join(m))
    footer = "This static report cannot verify itself. Reopen through the application before reuse; the source periods do not change. Contains public sector information licensed under the Open Government Licence v3.0."
    html.append(
        '<footer><p class="small">'
        + escape(footer)
        + ' <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">Data licence</a></p><p>'
        + escape(AUTHOR)
        + "</p></footer></main></body></html>\n"
    )
    md.extend([footer, AUTHOR])
    return {"brief.html": "".join(html), "brief.md": "\n\n".join(md) + "\n"}
