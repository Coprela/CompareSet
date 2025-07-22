# CompareSet

CompareSet is a tool for comparing vector-based PDF drawings. The project uses a
`src` layout for maintainability and includes a simple GUI built with PySide6.

## About

CompareSet was created for the DDT-FUE department at TechnipFMC and is intended
for use in authorized corporate environments.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# PyMuPDF 1.22 or newer is required
python -m compareset.ui.main_window
```
The application depends on [PyMuPDF](https://pypi.org/project/PyMuPDF/) version
1.22 or newer so that the two-argument ``Matrix`` constructor is available.

## Project layout

```
src/compareset/       - Library code
    ui/               - Graphical interface
    utils/            - Helper utilities
    i18n/             - Localization files
    config/           - Default application settings
assets/               - Icons and other static resources
tests/                - Pytest suite
```

## Environment

Configuration is loaded from environment variables. Copy `.env.example` to `.env`
and adjust as needed. Set `GITHUB_TOKEN` to a fine-grained personal access token
with **Contents: Read and Write** permission for the repository. Using
[python-dotenv](https://pypi.org/project/python-dotenv/) prevents secrets from
being committed.


## Packaging

For extra protection against reverse engineering, the build script attempts to
obfuscate sources with [PyArmor](https://pyarmor.readthedocs.io/). Install
PyArmor and PyInstaller then run the packaging script:

```bash
pip install pyarmor pyinstaller
python build_package.py
```
