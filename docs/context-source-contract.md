# Wider-market and economic source contracts

These optional context components use key-free official responses and retain literal source rows, period metadata, publication flags, labels, URLs and hashes. No occupation crosswalk, local salary model or tightness score is involved. Software remains AGPL-3.0-only; the original public statistics retain the [Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

## Local sources

| Source | Fixed selection | Population and quality |
| --- | --- | --- |
| [Nomis APS, NM_17_5](https://www.nomisweb.co.uk/datasets/apsnew) | Apr 2025–Mar 2026; variables 45, 111 and national 83; variable, numerator, denominator and confidence measures | Employment and inactivity use residents aged 16–64. National unemployment uses economically active residents aged 16+. Approximate 95% confidence margins retained. |
| [Nomis Claimant Count, NM_162_1](https://www.nomisweb.co.uk/datasets/ucjsa) | Total gender, all ages 16+; count and published proportion; July 2026 and July 2025 | Benefit claimants aged 16+ divided by residents aged 16–64. Not seasonally adjusted and not the unemployment rate. |
| [Nomis model-based unemployment, NM_127_1](https://www.nomisweb.co.uk/datasets/umb) | Apr 2025–Mar 2026, item 2, value and confidence | Unemployed residents aged 16+ relative to economically active residents aged 16+; local model estimate with approximate 95% margin. |

The Census occupation pack and these local sources have distinct geography contracts. Nomis TYPE424 identifies districts/unitary authorities as of April 2023. Original codes are retained, including Sheffield E08000019; no conversion to a newer district code is inferred. Claimant metadata contains 361 districts across the UK. APS and modelled unemployment contain 350 GB districts. Source presence does not promise usable estimates. The labelled UK benchmark is K02000001, not the Great Britain comparator used by some Nomis profiles. The model source has no UK observation: the national comparator is the same-window APS unemployment estimate. Different estimation methods remain explicit; no statistical test of their difference is calculated.

The model is preferable to unstable direct local APS unemployment for this purpose. It uses claimant information, so it is not independent corroboration. Employment, inactivity and unemployment have differing denominators/methods and must not be added. Inactivity is not recruitable supply. See the [ONS model guide](https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/methodologies/subnationallabourmarket/modelbasedestimatesunemploymenttcm77252969.pdf).

### Period and quality decisions

- APS and model observations were released 21 July 2026. APS metadata records start month 2025-04-01 and end month 2026-03-01. The published label is Apr 2025–Mar 2026; this is an annual window, not a March-only observation.
- Model metadata still contains literal `apsStartDate`/`apsEndDate` placeholders. These are preserved, not repaired. Its published period code and label match the APS window and were checked against the Nomis dataset/profile. Runtime qualification requires the recorded metadata contract.
- Claimants were counted on 9 July 2026 and 10 July 2025. The frozen current revision was released 18 August 2026; the prior-year revision was released 16 September 2025. The latest claimant month can be revised. Published proportions are used directly; the engine does not invent a denominator from rounded counts. Annual change is the difference in same-month published proportions, in percentage points. Eligibility and denominator revisions can affect it.
- Only normal source flags (`OBS_STATUS=A`, `OBS_CONF=F`) are publishable. Missing, suppressed and unreliable flags withhold the affected indicator comparison. Survey rates also require usable numerator, denominator and confidence cells. As an additional product presentation rule, a nonpositive margin or a margin at least as large as the estimate is withheld with a specific gap; this is not described as ONS suppression.
- An unavailable local/UK cell withholds that indicator for the selected comparison, not just the affected area. A missing prior claimant observation withholds change while keeping a valid current comparison. No replacement benchmark is inferred.
- No APS change is calculated across the [documented processing transition](https://www.nomisweb.co.uk/articles/1471.aspx). Overlapping confidence ranges are disclosed; non-overlap is not converted into a formal significance claim.

## Prices and average earnings growth

| Original ONS series | Displayed observation | Geographic scope |
| --- | --- | --- |
| [L55O, CPIH annual rate](https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/l55o/mm23) | 3.1%, twelve months to July 2026 | United Kingdom |
| [D7G7, CPI annual rate](https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23) | 2.9%, twelve months to July 2026 | United Kingdom |
| [KAI9, regular earnings growth](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kai9/lms) | 3.5%, April–June 2026 versus April–June 2025 | Great Britain, whole economy |
| [KAC3, total earnings growth](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/kac3/lms) | 4.1%, April–June 2026 versus April–June 2025 | Great Britain, whole economy |

The price release is 19 August 2026; earnings are from 18 August 2026. The original CSVs include history, but the product only qualifies the stated observations. It does not expose arbitrary series selection or silently move to a newer release. Values were cross-checked against the [July inflation bulletin](https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/july2026) and [August earnings bulletin](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/averageweeklyearningsingreatbritain/august2026).

CPIH includes owner occupiers’ housing costs and Council Tax; CPI excludes these. Neither is a local index or each household’s experienced inflation. Earnings growth is nominal, seasonally adjusted, and compares three-month average weekly earnings with the same three months a year earlier. Regular earnings exclude bonuses; total earnings include them. Both headline series exclude pay-award arrears. These are employee averages, not pay awards, and change with workforce composition, hours and payment timing. The latest month is provisional; adjusted estimates remain revisable. The selected CSVs contain no observation-level confidence interval, and none is invented.

The price and earnings windows differ. There is no subtraction to infer real earnings, compounding of annual rates, estimate of growth since April 2025, salary uplift or recommended increase. Historical ASHE observations remain unchanged. No sector-specific or financial-services growth is inferred from organisational context.

## Reproduction and independent traces

`context-sources.zip` contains the original Nomis CSVs and metadata; `economic-sources.zip` contains the original four ONS CSVs. Their references pin URLs, retrieval times and per-file/archive hashes. Source adapters pin the reference hashes, validate identities, periods and dimensions, and replay saved evidence. An unrecognised correction needs reviewed qualification; reports cannot approve their own source replacements.

`python -m scripts.check_context_source` checks 4,212 APS rows, 1,448 claimant rows and 700 model rows, then independently reads hand-traced original CSV lines for Sheffield and UK observations, auxiliary cells and all four economic figures. These are separate from production key selection. The Sheffield [Nomis profile](https://www.nomisweb.co.uk/reports/lmp/lad/1778385142/report.aspx) corroborated local rates; its GB comparison was not substituted for the UK API observation. Exact original lines and URNs appear in the check receipt and evidence ledger. Source errors produce explicit component gaps; independent families continue. The offline release gate also exercises installation and saved-report tamper detection.
