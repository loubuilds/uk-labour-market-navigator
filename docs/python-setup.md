# Getting Python ready

Your coding agent can handle most of this setup. Python runs the evidence checks; you do not need to learn to program in it.

Ask your agent:

> Check whether this computer has a suitable Python for UK Labour Market Navigator. If it needs installing, walk me through it, then return to my question.

## What happens next

| What the agent finds | Your next step |
| --- | --- |
| Python 3.11 or later is ready | Continue with your question. |
| A suitable version is installed but another opens by default | The agent uses the suitable version directly. No need to change your computer’s default. |
| Only an older Python, or no Python | Follow the agent’s short installation guidance, then continue. |
| A work computer restricts installation | Use your organisation’s approved route or ask IT. The worked example is readable while access is arranged. |

**The standard research workflow needs no extra Python libraries or data-provider account.** It uses Python’s built-in libraries. Developer tools are only for changing or testing code. Optional Adzuna has separate dependencies and is not part of first setup.

## If an installation is needed

Use a current stable release from [python.org](https://www.python.org/downloads/) or your organisation’s approved software catalogue. Choose a normal release, not a preview or experimental build. The project requires Python 3.11 or later; the [validation notes](validation.md) distinguish that requirement from platforms and versions actually tested.

- **Mac:** follow the [official macOS installer](https://www.python.org/downloads/macos/) prompts. When it finishes, open **Install Certificates.command** in the installed Python version's folder in Applications, and let it finish. This prepares Python for secure web connections. Then return to your agent. Apple’s developer tools can supply an older Python; leave that installation in place. Your agent can use the new one directly.
- **Windows:** use the [official Windows download route](https://www.python.org/downloads/windows/) or your organisation’s software catalogue. Your agent can find the installed version without asking you to edit PATH manually.
- **Linux:** use your distribution’s supported packages or approved software-management route. Your agent should check the distribution before suggesting an installation command.

An installer may ask you to approve changes. Complete that prompt yourself; never share an administrator password in chat. On a managed work device, follow the organisation’s installation process.

Then say **“Python is installed—please continue.”** Keep the same conversation so your question is still there. The agent should locate the new installation directly before asking you to reopen a terminal or application.

## A comfortable first step

> There’s one setup step before we begin. I’ll check whether a suitable Python is already installed and help you get it ready, then return to your question.

You should not have to choose package managers, interpret error traces or repeat your research question. Your agent should confirm that setup works before saying you are ready.

## Guidance for the coding agent

1. Inspect the platform and existing `.venv` or `.venv-local` interpreter. Discover executable paths before invoking them; the first `python` or `python3` may be too old. Probe actual executables with `--version`. Do not launch a Windows Store alias or Apple developer-tools installation prompt just to discover what is installed.
2. Look in a bounded set of existing installations. On Windows, inspect the available Python launcher’s supported listing command (`py --list-paths` for the traditional launcher; use its help for the install manager). On macOS, check versioned commands and existing `/Library/Frameworks/Python.framework/Versions/*/bin/python3*`, `/opt/homebrew/bin/python3*` and `/usr/local/bin/python3*`. On Linux, check versioned executables supplied by the system or an existing approved manager. Do not recursively search disks or read private configuration. Check the executable’s version rather than trusting its filename.
3. Reuse a supported, working environment. Preserve any old, broken or foreign-platform environment and choose a new unoccupied project-local environment path. Do not replace system Python, edit global PATH, add a package manager or upgrade unrelated projects just to run this repository.
4. If no suitable version exists, explain the one-time step and offer one appropriate official or organisation-approved route. Reuse existing installation authorisation. Explain any actual OS or IT approval needed, without repeated permission questions for routine project setup. Do not request credentials or bypass device policy. Never run an arbitrary downloaded shell installer.
5. Rediscover the executable after installation. Use its absolute path to create a project-local environment and use that environment’s interpreter consistently. Run `-m uk_labour_market_navigator help` separately and check its result. Source-checkout research needs no `pip install` or `[dev]` extras. A missing optional folder is not an installation failure; this version does not use profiles.
6. Some Linux distributions package `venv` separately. Explain the actual missing system package and use the approved distribution route. Research can also run directly from the checkout with a supported interpreter because the core has no third-party runtime dependencies. Do not claim an environment was created if it was not.
7. Offer one suitable stable installer, not a menu of versions and checksums. Verify its official origin in the background. Explain only the OS approval the person needs to complete. This project does not require changing the terminal's default Python or editing shell startup files. Do not advise deleting an entire existing startup file to undo an installer change.
8. For the python.org Mac installer, check that its **Install Certificates.command** step completed if secure web access is needed. If it was skipped, guide that same official step; never disable certificate verification. The bundled official research works offline and can continue while this is arranged. Do not test optional Adzuna access during setup. Certificate setup is part of that Python installation, not an extra evidence-engine library requirement.
9. Quote actual paths, including spaces and apostrophes. Diagnose the returned error before blaming a folder name. If the host cannot preview a local HTML file, provide the actual file link for normal browser opening; do not claim to have visually checked it, invent a hosted URL or copy research elsewhere without a reason and authorisation.
10. Resume the original question after verification. Keep routine commands and recovery details in the background. If installation is blocked, give one concrete next step and the readable example; do not label the project ready.

Python’s [macOS guide](https://docs.python.org/3/using/mac.html) explains separate Apple and python.org installations. The [Windows guide](https://docs.python.org/3/using/windows.html) covers current installation options. Check the relevant official instructions rather than reciting an outdated installer checkbox sequence.
