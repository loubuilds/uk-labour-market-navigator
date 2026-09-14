# Contributing

Thank you for helping make official labour-market evidence useful to People and Talent teams.

Start with a small issue or proposed change explaining the user problem. Use generic examples only: never submit credentials, client/employer research, personal information, private run folders or provider advert records. For a security concern, [request a private contact route](https://github.com/loubuilds/uk-labour-market-navigator/issues/new?title=Private%20security%20contact%20request) without including vulnerability details, credentials or affected data. Share the report only after a private route has been agreed.

Software contributions to this V0.1 edition use GNU AGPL v3.0 (AGPL-3.0-only); documentation uses CC BY-SA 4.0, and official data retains its source licence. Only contribute material you have authority to license. Preserve third-party notices. No CLA is required for V0.1. You retain copyright in your contributions. Contributing under these licences does not grant blanket permission to relicense your work under different terms.

Install Python 3.11 or newer, create a local virtual environment, and install with python -m pip install -e ".[dev]". Run python -m scripts.validate_release using that interpreter. The route runs tests, lint/format checks, source reproduction, hygiene and packaging. Keep official research and tests offline; provider tests must use synthetic responses and memory stores. Do not exercise a real account as part of CI.

Changes to source editions, taxonomy, population definitions, geographic scope or quality rules need an explicit source-contract update and independent traces. Do not invent crosswalks, estimates or hiring scores. Add meaningful regressions for changed behaviour. Preserve valid partial evidence. New narrative must distinguish checked figures from interpretation.

Do not manually edit verified reports. Regenerate the fictional Sheffield example with python -m scripts.make_example after an intentional renderer/source change, then re-run validation. Leave archived source-contract receipts as historical evidence.
