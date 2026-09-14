# V0.1 public preview

UK Labour Market Navigator turns a role-and-location question into a readable brief with checked official figures, AI-assisted interpretation and practical next steps. Start with the [fictional Sheffield example](https://loubuilds.github.io/uk-labour-market-navigator/) or bring your own question. See the [README](../README.md) for setup.

## Included in this release

- Historical resident workforce and employer advertising for whole occupations, with comparisons across up to three chosen districts.
- Separately accepted UK earnings and paid-hours benchmarks, wider local conditions, and national inflation and average earnings growth.
- An optional discussion before drafting, followed by self-contained HTML and Markdown reports with inspectable sources.
- Guided Python setup and a short example-or-hire welcome. No provider key or extra Python libraries are needed for the official source-checkout workflow.
- Offline source reproduction, saved-report verification and cross-platform release checks. Experimental user-owned Adzuna access remains separate from official reports.

## Coverage and limits

Source periods are frozen: Census 2021, advertising April-June 2026, ASHE 2025, and the local/economic periods in the [coverage matrix](coverage.md). There is no automatic refresh. Suppressed or missing evidence stays visible while independent supported sections continue.

UK earnings are national benchmarks, not district salaries. Whole occupations do not isolate specialist skills, seniority, commuting reach or available candidates. Advertising and claimant figures do not establish a shortage or a hiring diagnosis. Numerical and provenance checks do not prove an AI interpretation or replace professional judgement.

Windows, Linux and macOS run the same [release validation](validation.md). Optional-provider tests use synthetic responses; they do not establish permission or live account access. See [provider guidance](adzuna.md).

## Compatibility and recovery

Saved reports retain their recorded renderer so a later presentation change does not silently rewrite them. Unknown application or run identities cannot be repaired by editing their identity fields. Verification leaves files intact and withholds findings when checks fail. See [architecture](architecture.md) for the compatibility mechanism.

If collection or rendering is interrupted, retry that step: the workflow advances only after its outputs are written. Static reports retain their displayed dates. Git checkout rules preserve the exact qualified source and licence bytes across platforms.

Software uses **AGPL-3.0-only**; documentation and official data retain their separate licences. See [licensing](licensing.md).
