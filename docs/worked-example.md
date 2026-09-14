# Sheffield: a fictional hiring discussion

**Fictional worked example using public official statistics.**

> We’re a fictional financial-services organisation recruiting customer service advisers for an established, on-site team in Sheffield. After discussing recruitment challenges with stakeholders, we’re researching the business case for higher pay. What can official workforce, advertising, earnings, paid hours, wider labour-market conditions, inflation and average earnings growth contribute, what further evidence would strengthen the case, and which recruitment actions should we be able to demonstrate when presenting it?

## Occupation and scope

The bundled official SOC2020 classification lists customer service advisers under **7219: Customer service occupations n.e.c.** Here, n.e.c. means “not elsewhere classified”. This category covers work such as enquiries, accounts and complaints across industries. It is the broader starting view explicitly accepted for this demonstration, not an exact financial-services role match. The scenario does not specify a telephone-based contact-centre role; that work is separately classified under 7211 and would need a different investigation. Job duties determine the appropriate category.

The classification decision uses the original `SOC2020_volume1_descriptionofunitgroups.csv` in the bundled `soc2020.zip`, together with the pinned occupation identities. [ONS classification documentation](https://www.ons.gov.uk/methodology/classificationsandstandards/standardoccupationalclassificationsoc/soc2020/soc2020volume1structureanddescriptionsofunitgroups) explains the framework. Financial services is organisational context only; none of these figures isolates relevant industry experience, product knowledge or regulatory competence.

## What was used

| View | Scope | What it contributes |
| --- | --- | --- |
| Workforce | Sheffield district, whole occupation, Census 2021 employed residents | Historical scale and representation, not available candidates |
| Advertising | Sheffield on the source’s April 2023 districts, whole occupation, April–June 2026; June partly estimated | Advertising activity, not evidence of shortage or a count of distinct vacancies |
| Wider local conditions | Sheffield April 2023 district, all occupations, UK benchmarks | Claimant proportion/change, employment, inactivity and modelled unemployment; no tightness score |
| Prices and earnings growth | UK inflation; Great Britain whole-economy earnings growth | Separate dated context, not a salary uplift or individual pay award |
| Paid hours | UK full-time, whole occupation, April 2025 | Separate weekly-hours means (medians in the ledger), not the hours associated with median annual pay |
| Earnings | UK full-time employee jobs, whole occupation, ASHE 2025 provisional corrected edition | An explicitly accepted national annual benchmark, not a local offer or pay diagnosis |

All included evidence components have publishable observations for this example. The full-time annual benchmark is a comparison choice for the demonstration, not an invented contract or salary for the fictional vacancy. Its working hours and offer remain unspecified. Source labels, periods, quality and original cells are retained in the report.

The wider evidence challenges a simple low-claimant-rate argument: Sheffield is above the UK figure. Its modelled unemployment interval overlaps the UK survey estimate. National prices and earnings growth inform the pay-review discussion but are not applied to historical ASHE pay. The example uses the full context workflow; no statistics were inserted into its prose or outputs by hand. [Definitions and traces](context-source-contract.md).

## Reading the brief

The interpretation supports a stakeholder-informed business case for higher pay, distinguishing the contribution of local workforce and advertising context from the separate UK earnings benchmark. It recommends documenting relevant recruitment actions and what was learned before presenting the proposal. Those actions strengthen the recruitment argument; they are not a prerequisite for a fair-pay review. The final questions suggest examining applicant progression and drop-off, withdrawal and rejection reasons, working hours, on-site travel requirements, role requirements and relevant current pay evidence. They also suggest checking whether adverts and recruitment marketing communicate the full employment offer, and reviewing how comparable local employers present theirs. Reviews, ratings and social content are selective signals, not proof of hiring success. These are external investigations; the example contains no applicant totals, funnel results, salary, headcount, competitor research or employer findings. In a real investigation, an [optional discussion before drafting](discussing-your-brief.md) helps tailor these suggestions.

Open the [live designed brief](https://loubuilds.github.io/uk-labour-market-navigator/), or inspect the [Markdown version on GitHub](../examples/brief.md). Interpretation comes before the detailed tables. The README uses a chart excerpt extracted from this report. Maintainers can follow the [hosting guide](example-hosting.md) to update the live example. The files are generated through the existing evidence workflow from `examples/request.json` and `examples/synthesis.json`; `python -m scripts.make_example --check` independently regenerates and compares them.

The first pass uses concise decision cards, a resident-workforce chart, comparison tables and practical next steps. Detailed definitions and source records are expandable. Paid hours sit in a separate table from earnings, with the pairing distinction beside the figures. Mean hours include jobs with no paid overtime, keeping the main comparison consistent. Medians and their different overtime population remain inspectable in the ledger.
