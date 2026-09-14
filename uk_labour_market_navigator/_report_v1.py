"""Self-contained report: checked facts plus explicitly attributed host synthesis."""

from __future__ import annotations

from decimal import Decimal
from html import escape

from .evidence import canonical

CSS = """
:root{--ink:#173448;--teal:#006d68;--muted:#526773;--line:#d8e2de}
*{box-sizing:border-box}body{margin:0;background:#f5f5ef;color:var(--ink);font:17px/1.65 system-ui,sans-serif}
main{max-width:1040px;margin:auto;padding:34px 24px 70px}.brand{font-size:12px;font-weight:750;letter-spacing:.14em;
color:var(--teal);text-transform:uppercase}header{border-top:6px solid var(--teal);padding:28px 0}
h1{font-size:clamp(2rem,5vw,3.1rem);line-height:1.12;max-width:24ch;letter-spacing:-.03em;margin:14px 0}
h2{font-size:1.45rem;line-height:1.3}h3{font-size:1.06rem}p{max-width:82ch}.lead{font-size:1.18rem}
.label{font-size:.8rem;color:var(--muted);font-weight:700;letter-spacing:.05em;text-transform:uppercase}
.panel{background:white;border:1px solid var(--line);border-radius:12px;margin:20px 0;padding:26px}
.scope{border-left:3px solid var(--teal);padding-left:16px;color:var(--muted);font-size:.93rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}.card{padding:18px;background:#eef5f1;border-radius:8px}
.value{font-size:2rem;line-height:1.2;font-weight:750;display:block}.card p{margin:8px 0 0;font-size:.9rem}
svg{width:100%;height:auto}svg text{fill:var(--ink);font-family:system-ui,sans-serif}.table{overflow:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem;font-variant-numeric:tabular-nums}th,td{padding:12px;text-align:right;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}thead{background:#edf3ef}caption{text-align:left;color:var(--muted)}
a{color:var(--teal);overflow-wrap:anywhere;text-underline-offset:3px}li{margin:10px 0}.cite{font-size:.82rem}
.open{border-left:4px solid #b67b28}.small{font-size:.88rem;color:var(--muted)}summary{cursor:pointer;font-weight:700;padding:12px 0}
details{border-top:1px solid var(--line);margin-top:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:.8rem/1.5 ui-monospace,monospace}
:focus-visible{outline:3px solid #a96800;outline-offset:3px}@media(max-width:600px){main{padding:20px 14px}.panel{padding:20px 16px}}
@media print{body{background:white;font-size:10pt}main{padding:0}.panel{border-radius:0}details>*{display:block!important}.table{overflow:visible}tr{break-inside:avoid}}
"""


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
        f"<figure><figcaption>{escape(title)} Â· Census 2021</figcaption>",
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
    facts = {f["id"]: f for f in evidence["facts"]}
    rows = evidence["rows"]

    def citation_label(fact_id):
        place_id, measure = fact_id.split(".")
        labels = {
            "count": "workforce size",
            "share": "local employment share",
            "concentration": "relative concentration",
            "benchmark_count": "England and Wales workforce size",
            "benchmark_share": "England and Wales benchmark share",
        }
        if measure.startswith("benchmark"):
            return labels[measure]
        place = next(row["place"] for row in rows if row["id"] == place_id)
        return place + ": " + labels[measure]

    role = evidence["scope"]["occupation"]["label"]
    names = ", ".join(r["place"] for r in rows)
    scope = (
        f"{role} in {names}. Census Day: 21 March 2021. Usual residents aged 16+ in employment; "
        "whole occupation, all seniority levels. District boundaries as tabulated in the May 2023 release. "
        "These are employed residents, not people available to hire or a commuting catchment."
    )
    html = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{escape(draft['title'])}</title><style>{CSS}</style></head><body><main><header>",
        '<div class="brand">UK Labour Market Navigator / Research brief</div>',
        f'<h1>{escape(draft["title"])}</h1><p class="lead">{escape(draft["opening"])}</p>',
        '<p class="small">A discussion brief: source figures are checked; the explanation and suggested next questions are agent-authored interpretation.</p>',
        f'<p class="scope">{escape(scope)}</p></header>',
    ]
    md = [
        "# " + draft["title"],
        draft["opening"],
        "Agent-authored discussion brief; source figures checked separately.",
        scope,
        "## Your question",
        plan["question"],
        "Purpose: " + plan["purpose"],
        "## What the evidence shows",
    ]
    html.append(
        '<section class="panel"><div class="label">Checked evidence</div><h2>A starting picture of this workforce</h2>'
    )
    if len(rows) == 1:
        row = rows[0]
        html.append('<div class="cards">')
        cards = [
            (f"{Decimal(row['count']):,.0f}", "Employed residents", row["place"]),
            (
                f"{Decimal(row['share']):.1f}%",
                "Share of local employment",
                f"England and Wales: {Decimal(row['benchmark_share']):.1f}%",
            ),
            (
                f"{Decimal(row['concentration']):.2f}x",
                "Relative concentration",
                f"Rounding range {row['rounding_low']} to {row['rounding_high']}; not a confidence interval",
            ),
        ]
        for value, label, note in cards:
            html.append(
                f'<div class="card"><span class="value">{escape(value)}</span><strong>{label}</strong><p>{escape(note)}</p></div>'
            )
        html.append("</div>")
    html.extend(
        [
            chart(rows),
            '<div class="table"><table><caption>Population size and concentration are different measures.</caption><thead><tr><th scope="col">District</th><th scope="col">Employed residents</th><th scope="col">Local share</th><th scope="col">E&amp;W share</th><th scope="col">Concentration</th><th scope="col">Rounding range</th></tr></thead><tbody>',
        ]
    )
    md.extend(
        [
            "| District | Employed residents | Local share | E&W share | Concentration | Rounding range |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        cells = [
            row["place"],
            f"{Decimal(row['count']):,.0f}",
            row["share"] + "%",
            row["benchmark_share"] + "%",
            row["concentration"] + "x",
            row["rounding_low"] + " to " + row["rounding_high"],
        ]
        html.append(
            '<tr><th scope="row">'
            + escape(cells[0])
            + "</th>"
            + "".join("<td>" + escape(c) + "</td>" for c in cells[1:])
            + "</tr>"
        )
        md.append("| " + " | ".join(cells) + " |")
    precision = "Counts are rounded to five; shares to one decimal place. Concentration uses rounded local and benchmark shares. Its range represents rounding, not survey confidence. There is no overall location score."
    html.append('</tbody></table></div><p class="small">' + precision + "</p></section>")
    md.extend(
        [
            precision,
            "## What to take into your discussion",
            "The following interpretation is written by the host agent, not verified as a source fact.",
        ]
    )
    html.append(
        '<section class="panel"><div class="label">For your discussion Â· agent interpretation</div><h2>What to take into the conversation</h2>'
    )
    for section in draft["sections"]:
        html.append(
            "<h3>"
            + escape(section["heading"])
            + "</h3><p>"
            + escape(section["text"])
            + '</p><p class="cite">Evidence: '
        )
        html.append(
            " Â· ".join(
                f'<a href="#fact-{escape(i, quote=True)}">{escape(citation_label(i))}</a>' for i in section["fact_ids"]
            )
        )
        html.append("</p>")
        md.extend(
            [
                "### " + section["heading"],
                section["text"],
                "Evidence: " + ", ".join(citation_label(i) for i in section["fact_ids"]),
            ]
        )
    html.append("</section>")
    gaps = list(
        dict.fromkeys(
            [
                *plan["gaps"],
                "Current availability, seniority, skills and hiring causes are not measured by this Census occupation evidence.",
                "Pay, current job advertising and wider indicators have not been included in this first working slice.",
            ]
        )
    )
    html.append(
        '<section class="panel open"><h2>What remains open</h2><ul>'
        + "".join("<li>" + escape(g) + "</li>" for g in gaps)
        + "</ul></section>"
    )
    md.extend(["## What remains open", *["- " + g for g in gaps]])
    html.append(
        '<section class="panel"><h2>A useful next conversation</h2><ul>'
        + "".join("<li>" + escape(q) + "</li>" for q in draft["next_questions"])
        + '</ul><p class="small">You can also ask to compare another district, change the occupation, or show the sources. Other evidence routes remain planned.</p></section>'
    )
    md.extend(["## A useful next conversation", *["- " + q for q in draft["next_questions"]]])
    url = evidence["source"]["source_page"]
    html.append(
        '<section class="panel"><h2>Sources and evidence ledger</h2><p><a href="'
        + escape(url, quote=True)
        + '">ONS Census occupation tables, released May 2023</a></p>'
    )
    html.append(
        '<p class="small">The snapshot has not been refreshed live. Reopen through the application to reverify it; this static page cannot check itself.</p>'
    )
    md.extend(["## Evidence ledger", "Source: " + url])
    for fact in facts.values():
        html.append(
            '<details id="fact-'
            + escape(fact["id"], quote=True)
            + '"><summary>'
            + escape(fact["display"])
            + "</summary><pre>"
            + escape(canonical(fact))
            + "</pre></details>"
        )
        md.extend(
            [
                "### " + fact["id"],
                fact["display"],
                "Population: " + fact["population"],
                "Period: " + fact["period"],
                "```json\n" + canonical(fact) + "```",
            ]
        )
    html.append(
        "<details><summary>Full scope, methodology and provenance</summary><pre>"
        + escape(
            canonical(
                {
                    "scope": evidence["scope"],
                    "source": evidence["source"],
                    "caveats": evidence["caveats"],
                    "question": plan["question"],
                    "purpose": plan["purpose"],
                }
            )
        )
        + "</pre></details></section></main></body></html>\n"
    )
    md.extend(
        [
            "## Methodology",
            *evidence["caveats"],
            "Source provenance:\n```json\n" + canonical(evidence["source"]) + "```",
        ]
    )
    return {"brief.html": "".join(html), "brief.md": "\n\n".join(md) + "\n"}
