# Official employer demand: integrated source contract

Source: [ONS labour demand volumes by SOC2020](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/labourdemandvolumesbystandardoccupationclassificationsoc2020uk),
21 August 2026 edition, January 2017 to July 2026 workbook. The page was checked
12 September 2026. Runtime uses the reproduced qualified bundle, not a live refresh.
The workbook and runtime pack retain the hashes in uk_labour_market_navigator/resources/advertising-reference.json.

Table 5, column AR, contains April to June 2026 new online adverts by four-digit
SOC2020 occupation and April 2023 district. Original labels and codes are preserved;
all 412 occupation identities match the official SOC2020 registry. There is no
SOC2010 crosswalk. Model assignment of advert titles remains a source limitation.

The workbook's cover notes take precedence over the older methodology overview:
live-advert snapshots have been withdrawn since the 26 September 2025 release.
The implemented measure is new advertising during a quarter.
June is partially imputed; uncertainty has increased since November 2025; March
2026 is suppressed. No growth, live-vacancy or shortage measure is calculated.

Data contains 133,853 classified district observations, of which 74,274 Q2 cells
are suppressed. London region rows and unknown occupations are not assigned to
districts or roles. Suppression remains a gap, not zero. Any unusable selected
district withholds that entire advertising comparison; independently supported
workforce context survives. The same rule applies in reverse when Census is missing.

Each investigation proposes advertising's April 2023 districts separately from
Census boundaries before the person accepts the combined plan. No code-only
geography conversion is hidden. Demand-only queries can use supported Scottish
and Northern Irish districts; this does not imply Census or pay coverage there.

The report keeps the two populations and periods separate. Recent new-advert
counts divided by Census 2021 residents would not measure competition, vacancy
rates or candidate availability; no such ratio, ranking score or causal verdict
is implemented. Neither a quarter total nor a company-name sample counts distinct
employers competing for a particular candidate.

Redistribution is limited to ONS-published aggregate tables under their OGL terms.
No raw Textkernel feed or provider account is used. The literal workbook extractor
rejects data formulas and pins the release bytes. Runtime verifies independently
pinned reference and pack hashes; re-opening a report recomputes both evidence
sections and checks all readable files. Saved reports keep their recorded renderer. See [architecture.md](architecture.md)
for the current format and compatibility policy.

Reproduce with `python -m scripts.check_demand_source`. The complete pack,
place/occupation registry, suppression count and compressed bytes must agree.
Direct source cell checks include Reading AR71999 = 338, Cambridge AR20906 = 705,
City of Edinburgh AR57354 = 455 and Belfast AR53697 = 489, all SOC2020 2134.
These are source observations, not user/client research examples.
