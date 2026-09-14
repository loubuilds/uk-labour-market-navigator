# Third-party and data notices

## Office for National Statistics

Contains public sector information licensed under the Open Government Licence v3.0.
https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

The official Census occupation workbook, SOC2020 archive, ONS-published Textkernel advertising aggregates, ASHE Table 14 archive, Nomis local-context responses and ONS prices/earnings-growth CSVs, their source registries and derived compressed packs reside in uk_labour_market_navigator/resources/. Each reference file records the source URL, edition and hashes. Source data remains under its own terms, not AGPL. We do not redistribute a raw Textkernel feed. There is no endorsement by ONS or government.

## Software and prior work

V0.1 software: Copyright © 2026 Louise Mead, GNU AGPL v3.0 (AGPL-3.0-only). Software adapted from earlier work by Louise retains its ownership provenance. Earlier grants are not retrospectively revoked by this release. Official source URLs, versions and hashes remain in the bundled reference files; see docs/methodology.md.

## Optional Adzuna

Experimental BYOK connector only. Adzuna data is not bundled. No API access or data-use right is granted by this repository's software licence. Users must review their intended use and their own provider terms; see docs/provider-permissions.md. No advert publication, caching or official-report inclusion is implemented.

## Python dependencies

The official runtime uses Python's standard library and has no third-party runtime dependency. Python carries its own PSF licence. Optional keyring is separately installed and carries its project licence (MIT); its platform dependencies retain their own notices. Setuptools, pytest and Ruff are development/build tools, not vendored software. The built package contains this project's code, notices and public source inputs; dependency installation remains subject to each dependency's licence.
