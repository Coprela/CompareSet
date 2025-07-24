# CompareSet

CompareSet is a tool for comparing vector-based PDF drawings. The project uses a
`src` layout for maintainability and includes a simple GUI built with PySide6.

## About

CompareSet was created for the DDT-FUE department at TechnipFMC and is intended
for use in authorized corporate environments.

## Quick start

```bash
pip install -r requirements.txt
python run_app.py
```
PyMuPDF 1.22 or newer is required for PDF processing.
The interface layouts are defined as Qt Designer `.ui` files in `src/compareset/ui` and styled by `assets/style.qss` for a consistent look.

The former monolithic script ``main_interface.py`` is deprecated and kept only
for reference. Use ``python -m compareset`` or the ``run_app.py`` helper as the
application entry point.

## Project layout

```
src/compareset/       - Library code
    ui/               - Graphical interface
    utils/            - Helper utilities
    i18n/             - Localization files
    config/           - Default application settings
assets/               - Icons and other static resources
tests/                - Pytest suite
docs/                 - Additional documentation
```

See the `docs/` directory for architectural notes and customization tips.

## Environment

Configuration is loaded from environment variables. Copy `.env.example` to `.env`
and adjust as needed. Set `GITHUB_TOKEN` to a fine-grained personal access token
with **Contents: Read and Write** permission for the repository. Using
[python-dotenv](https://pypi.org/project/python-dotenv/) prevents secrets from
being committed.

| Variable | Purpose |
|----------|---------|
| `GITHUB_REPO` | Repository used to fetch remote configuration |
| `GITHUB_TOKEN` | Personal access token for the repository |
| `GITHUB_API_BASE` | Base URL for the GitHub API |
| `GITHUB_PATH_PREFIX` | Path inside the repo for config files |
| `LATEST_VERSION_FILE` | JSON file with the latest version information |
| `ALLOWED_USERS_FILE` | Remote user list file |
| `ADMIN_MODE` | Set to `1` to enable admin features |
| `LANG` | Force interface language (`pt` or `en`) |
| `SIGNTOOL` | Path to signtool.exe for signing builds |
| `SIGN_CERT` | Code signing certificate (.pfx) |
| `SIGN_PASS` | Password for the signing certificate |
| `SIGN_TIMESTAMP` | Timestamp URL used when signing |


## Packaging

For extra protection against reverse engineering, the build script attempts to
obfuscate sources with [PyArmor](https://pyarmor.readthedocs.io/). Install
PyArmor 7 and PyInstaller then run the packaging script:

```bash
pip install pyinstaller pyarmor==7.6.1
python build_package.py
```

## Contributing

Run the test suite with `pytest` to verify changes. PyMuPDF must be installed
for the tests to run. Without it the suite will be skipped.
Formatting is enforced with `black` and `flake8`. Type checking uses `mypy`:

```bash
black .
flake8
mypy
pytest
```
