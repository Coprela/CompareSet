# CompareSet

CompareSet is a tool for comparing vector-based PDF drawings. The project uses a
`src` layout for maintainability and includes a simple GUI built with PySide6.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m compareset.ui.main_window
```

## Project layout

```
src/compareset/       - Library code
    core/             - Comparison engine
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

### Local server

For convenience a small FastAPI server (`server.py`) can proxy access to
`usuarios.json`. It runs on `localhost` using port `SERVER_PORT` (default 5020).
Set `SERVER_API_TOKEN` to restrict access to clients that send the matching
header value.

## Packaging

To create a standalone executable you can use [PyInstaller](https://www.pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile -n compareset src/compareset/ui/main_window.py
```
