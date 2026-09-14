# Repeatable release validation

From a clone, use Python 3.11+ in a local virtual environment. Install maintainer dependencies with `python -m pip install ".[dev]"`, then run:

```sh
python -m scripts.validate_release
```

Use the actual environment interpreter, not a different system Python. The declared development dependencies include setuptools 77 or later: the release build uses `--no-isolation`, so that build dependency must already be installed in this environment. Ordinary research from the checkout does not need these maintainer dependencies. The validation command runs tests, Ruff lint/format checks, every Census/advertising/pay/hours/local-context/economic source reproduction, the fictional Sheffield example replay, tracked-tree/reachable-history pattern and path checks, wheel/source distribution builds, package-content/licence checks, and a fresh offline wheel-install smoke journey. It never calls Adzuna or reads credentials. Source validation must not run under Python optimisation, which disables assertions.

The result is `runs/release-validation.json`, created locally and excluded from Git. It records the actual revision, command outcomes, source counts and built-artifact SHA256 hashes. Distribution files are in `dist/v0.1rc6/`. Both folders are outputs, not prerequisites in a fresh clone. A failed command fails the validation route. Git author metadata is checked without printing personal values. Manual review of the public files and commit identity complements the automated pattern checks.

The clean-install check creates a new temporary virtual environment, installs the built wheel with `--no-index --no-deps`, changes to a separate temporary directory and uses isolated Python mode. It checks the import comes from that environment, blocks socket connections and exercises setup/help plus five question-to-report/reverification journeys. It checks source-only gaps, specialist requirements, corrected pay suppression, wider local conditions and national price/earnings context. Mixed-nation cases verify that unavailable survey/model comparisons remain gaps while claimants and independent evidence continue. It does not claim to test a particular coding agent's natural-language judgement or UI.

The full release gate has passed on **Windows/Python 3.12**, **Linux/Python 3.11** and **macOS/Python 3.14**, including source reproduction, example consistency and fresh offline installation. CI runs the same gate on those three platforms; consult the result for the selected commit. The Windows junction and redirected-input regressions also passed on Python 3.11. These automated checks do not exercise the macOS installer or establish that every coding agent provides a comfortable conversation. The engine uses standard-library portable Python, but platform-specific optional credential stores are not part of the official clean-install claim.

To reproduce just the fictional Sheffield report:

```sh
python -m scripts.make_example --check
```

Without `--check`, this regenerates tracked example outputs from the explicitly accepted synthetic request/draft. It starts a temporary run, collects real qualified source facts, publishes locally and reverifies before comparing/copying outputs. The chart preview is extracted from the generated HTML and compared too. It never reuses private research. A static example is for reading; this command is its reproducibility check.

Source-only commands are `python -m scripts.check_source`, `python -m scripts.check_demand_source` `python -m scripts.check_pay_source` and `python -m scripts.check_context_source`. Pay includes independent raw XML traces; the production extractor is not its only oracle. All operate on the bundled original public files.

Automated privacy pattern checks supplement manual review of prose, paths, provenance, archives and Git identity. They do not certify that arbitrary confidential information is absent. Human usability and interpretation review remain separate.

For static-hosting preparation, see [example-hosting.md](example-hosting.md). The local preparation command checks the example and writes only its HTML to a new output directory. A local preparation pass is not a deployed-site or human usability test.

The bootstrap regressions simulate Python 3.9.6 and 3.10 version selection in isolated processes, verify a friendly exit before engine/provider imports, and check that no research files are created. Bootstrap syntax is also parsed using Python 3.9 grammar. These checks do not claim to run the engine on unsupported Python or exercise the macOS installer. The ordinary help/setup path is exercised on the actual validation interpreter.

Temporary validation directories are canonicalised immediately after creation, including pytest-owned roots. This accommodates macOS's system `/var` alias without resolving arbitrary user research paths. The engine still rejects links and Windows junctions in research paths or their ancestors. Regression tests reproduce the example through a linked temp ancestor, check the install harness receives a physical root, and reject reading, writing or starting research through an internal link. The install-harness regression mocks process creation; the full gate separately performs the real offline wheel installation.
