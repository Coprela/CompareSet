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
Windows users can simply double-click ``run_app.py`` after installing the
requirements; no virtual environment is required.
PyMuPDF 1.22 or newer is required for PDF processing.
The interface layouts are defined as Qt Designer `.ui` files in `src/compareset/ui` and styled by `assets/style.qss` for a consistent look.
Pages from the newer document are automatically normalized to the coordinate
space of the reference PDF so highlights align correctly.

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
