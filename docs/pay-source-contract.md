# V0.1 official pay contract

Qualified 12 September 2026: ONS ASHE Table 14, 2025 provisional, released 23 October 2025, correction 19 December 2025. Source page and exact archive hash are in uk_labour_market_navigator/resources/pay-reference.json. The public ONS dataset page and 2025 earnings bulletin were checked on qualification. Original archive bytes match the previously qualified public-source archive.

## Taxonomy and accepted scope

The historical dataset URL contains SOC2010. The selected workbooks explicitly declare SOC20 (4); all 412 codes match the installed official SOC2020 registry. This is same-vintage, same-code identity, one-to-one at unit-group level. Preserve the pay source label separately. No SOC2010 crosswalk or model-generated correspondence is used. Unsupported or incompatible classification remains a gap.

V0.1 offers UK-wide workplace occupation pay only. It is not pay for the selected district or a specialist vacancy. The initial proposal states UK geography, official whole occupation, working pattern and measure. The user must agree to the pay scope separately from the workforce/demand scope. Declining UK pay produces no substitute. For a location comparison the same UK benchmark appears once, never as different local salaries.

All sexes combined; all, full-time or part-time employee jobs. Annual gross earnings cover the tax year ending 5 April 2025, adult rates and the same job for more than a year, including pay affected by absence. Hourly earnings excluding overtime cover the pay period including 30 April 2025, adult rates and pay unaffected by absence. No hourly-to-annual conversion. Full-time is more than 30 paid hours weekly or at least 25 for teaching professions.

## Quality and reproduction

Median, 25th and 75th percentile each require their own source estimate and matching CV. Preserve missing/suppressed/nil-or-negligible markers; never zero-fill. CV above 20 percent withholds a value. Up to 5 percent is precise, over 5 to 10 reasonably precise, over 10 to 20 acceptable under the inherited reviewed ASHE quality contract. These are source precision bands, not model confidence. Percentiles describe earnings dispersion, not recommended offers or confidence intervals.

Annual display precision is whole pounds; hourly two decimals; CV one decimal. Extraction checks workbook formats. Only machine-decimal differences within 0.00000001 of display precision are normalised. All 2472 records reproduce from 412 occupations, three patterns and two measures. The December correction retains suppressed annual police-officer observations (3312). No local adjustment, pooling, trend, offer recommendation or advertised-salary equivalence.

Source data remains ONS/Open Government Licence v3.0. The extractor and original source archives are included for reproducibility. Run python -m scripts.check_pay_source for the complete offline reproduction and independent cell traces. This frozen edition does not promise the newest observation on reopening.

## Source-title differences found during all-occupation regression

The newer pinned SOC registry and Census 2023 workbook have eight title differences at the same SOC2020 unit codes: 8211, 5223, 2122, 2212, 6129, 3131, 2124 and 6121. Original titles are explicit in evidence.CENSUS_LABELS and verified against every source row. This is no allocation/crosswalk: each figure remains the literal observation for its source code and source title. The proposal, workforce figures and limitations preserve the historical title; matching codes do not claim identical current duties. In particular 6121 (Census Pest control officers, registry Pest controllers) is one of the 78 zero-benchmark roles and must not lose valid counts merely because the newer title differs. Further materially changed role requirements remain a gap, not inferred equivalence.

ASHE has 25 literal title differences against the newer common SOC registry. Its source label is preserved in the common source-specific identity registry, the pay option, the proposal before the user agrees, the visible earnings section and every source cell. The same SOC2020 code identifies a published unit; differing wording is not a claim that current duties or specialist scope are unchanged. The engine cannot create a current specialist subset from this historical unit.

Official qualification references: [ONS ASHE Table 14 and correction notice](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/occupation4digitsoc2010ashetable14) and [Employee earnings in the UK: 2025](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/bulletins/annualsurveyofhoursandearnings/2025). The archive identity is recorded in pay-reference.json; opening a changing dataset page is not itself a refresh of this qualified edition.

## Components of earnings

Annual gross earnings include overtime and bonus or incentive payments, before tax, National Insurance and other deductions; benefits in kind are excluded. This is not a basic-salary benchmark. The hourly option excludes overtime but is not a basic-pay-only measure. These definitions apply to all displayed percentiles, not only the median.

The [ONS guide to interpreting ASHE](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/methodologies/guidetointerpretingannualsurveyofhoursandearningsasheestimates) defines gross pay and its components. The [questionnaire guidance](https://www.ons.gov.uk/surveys/informationforbusinesses/businesssurveys/additionalguidancefortheannualsurveyofhoursandearningspaperquestionnaire) specifies the preceding tax year for annual earnings. The annual figure is income over that year, not the basic salary in force on its final day. This clarification changes no source observations or calculation.

## Separately scoped weekly paid hours

Qualified 14 September 2026 from the same original corrected 2025 ASHE archive, with no change to the earnings pack. Tables 14.9 (total), 14.10 (basic) and 14.11 (overtime), estimate and CV workbooks, explicitly declare four-digit SOC2020. All 412 codes and original pay-source labels align; no crosswalk is used. All/full-time/part-time employee jobs are separate. The population is adult rates, pay unaffected by absence, pay period including 30 April 2025; hours are expressed per week. Annual earnings use a different period and eligibility definition.

The bounded hours pack contains 3,708 occupation/pattern/measure records, with median (D) and mean (F) estimates and matching CVs. Original workbooks and their hashes remain bundled; hours.json.gz is pinned independently in hours.py. One-decimal values/CVs use the existing precision and suppression gate. Missing/suppressed and nil-or-negligible cells are not zero-filled. A CV above twenty percent withholds that estimate only. No generated pack can approve its own source replacement.

Overtime workbook footnote: medians and percentiles exclude zero responses, whereas means include them. Thus overtime median is among nonzero paid-overtime responses, while the mean includes eligible jobs with none. No subtraction or addition of medians, pairing with earnings, annualisation, salary conversion or minimum-wage compliance calculation is supported. Paid hours exclude unpaid work. A zero CV is the publisher's rounded value, not proof of an error-free estimate.

Independent raw XML traces at Full-Time row 458 (SOC2020 7219) check both D and F: basic median 37.3 and mean 37.2; total median 37.4 and mean 37.8; overtime median 2.3 and mean 0.6 hours/week. The script checks their original estimate and CV cells independently of the production worksheet parser. Run `python -m scripts.check_hours_source` for full pack reproduction and traces. All figures retain UK whole-occupation and working-pattern scope; no fictional vacancy hours are supplied.
