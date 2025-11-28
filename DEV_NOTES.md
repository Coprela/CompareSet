# CompareSet quick mapping

## Entrypoint
- The application starts from `compare_set_gui.py` with the `main()` function guarded by `if __name__ == "__main__":`.
- `main()` creates the Qt application, runs access/update/install checks, initializes the environment via `compareset_env.initialize_environment()`, and brings up `MainWindow`.

## Current flow
- In the UI the user selects OLD and NEW PDFs, then clicks **Compare**.
- A `CompareSetWorker` wraps `compareset_engine.run_comparison()` in a background `QThread` and emits `ComparisonResult`.
- On completion, the GUI saves a temp copy of the inputs plus the generated result PDF (from `ComparisonResult.pdf_bytes`) into `%LOCALAPPDATA%\CompareSet\temp\{job_id}` and appends a structured entry to the history JSON; it also attempts to push a JSON log to the server.
- The result path from `ComparisonResult.server_result_path` is still reported to the user for legacy workflows.

## Storage layout (local vs server)
- Server UNC roots come from `compareset_env`: `SERVER_RESULTS_ROOT`, `SERVER_LOGS_ROOT`, `SERVER_RELEASED_ROOT`, etc.
- Local base is `%LOCALAPPDATA%\CompareSet` with subfolders for `history/`, `logs/`, `output/`, `config/`, `released/`, `temp/`, and `update/` defined in `compareset_env`.
- `history_service.py` keeps `history.json` under `history/` and per-job artifacts under `temp/{job_id}` (OLD/NEW/RESULTADO.pdf).
- Engine logs use `compareset_engine.init_log/write_log` targeting per-user files under `LOG_DIR` (server or local depending on connectivity).

## Connectivity
- Connectivity is detected via `compareset_env.is_server_available()` and propagated with `set_connection_state`; `ConnectionMonitor` runs periodic checks emitting status changes to the UI.
- When offline or forced into local storage, paths are switched to the local `%LOCALAPPDATA%\CompareSet` tree; otherwise UNC server paths are used.
- Access control and version manifest fetches go through `server_io` (UNC or HTTP JSON files).

## Server interactions
- Access control reads `access.json` and blocks the UI if the user is not listed.
- Update checks read `version.json`; optional download replaces `%LOCALAPPDATA%\CompareSet\CompareSet.exe`.
- After a comparison, `server_io.persist_server_log` pushes a small JSON log; releasing a PDF uses `server_io.send_released_pdf`.
