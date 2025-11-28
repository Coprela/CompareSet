"""Local history store for CompareSet jobs."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Literal

import compareset_env as csenv

HistoryStatus = Literal["ENVIADO", "PENDENTE", "ERRO"]
ReleaseStatus = Literal["NAO_LIBERADO", "LIBERADO", "ERRO"]


@dataclass
class HistoryEntry:
    job_id: str
    timestamp: str
    old_path_local: str
    new_path_local: str
    result_path_local: str
    server_log_status: HistoryStatus = "PENDENTE"
    server_released_status: ReleaseStatus = "NAO_LIBERADO"
    server_log_message: str = ""
    server_released_message: str = ""


def _history_path() -> Path:
    return Path(csenv.LOCAL_HISTORY_DIR) / "history.json"


def ensure_history_storage() -> None:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")


def load_history() -> List[HistoryEntry]:
    ensure_history_storage()
    try:
        with open(_history_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return []
    entries: List[HistoryEntry] = []
    for item in data if isinstance(data, list) else []:
        try:
            entries.append(HistoryEntry(**item))
        except Exception:
            continue
    return entries


def save_history(entries: List[HistoryEntry]) -> None:
    ensure_history_storage()
    payload = [asdict(entry) for entry in entries]
    with open(_history_path(), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def append_entry(entry: HistoryEntry) -> None:
    entries = load_history()
    entries.append(entry)
    save_history(entries)


def update_entry_status(
    job_id: str,
    *,
    log_status: HistoryStatus | None = None,
    release_status: ReleaseStatus | None = None,
    log_message: str | None = None,
    release_message: str | None = None,
) -> None:
    entries = load_history()
    updated = False
    for entry in entries:
        if entry.job_id == job_id:
            if log_status is not None:
                entry.server_log_status = log_status
            if log_message is not None:
                entry.server_log_message = log_message
            if release_status is not None:
                entry.server_released_status = release_status
            if release_message is not None:
                entry.server_released_message = release_message
            updated = True
            break
    if updated:
        save_history(entries)


def clear_history_and_temp() -> None:
    history_file = _history_path()
    if history_file.exists():
        history_file.unlink()
    if os.path.isdir(csenv.LOCAL_TEMP_DIR):
        for child in Path(csenv.LOCAL_TEMP_DIR).iterdir():
            if child.is_dir():
                for nested in child.iterdir():
                    try:
                        nested.unlink()
                    except Exception:
                        pass
                try:
                    child.rmdir()
                except Exception:
                    pass
    if os.path.isdir(csenv.LOCAL_TEMP_DIR):
        try:
            os.rmdir(csenv.LOCAL_TEMP_DIR)
        except Exception:
            pass


def temp_dir_for_job(job_id: str) -> Path:
    return Path(csenv.LOCAL_TEMP_DIR) / job_id


def build_history_entry(job_id: str, old_path: Path, new_path: Path, result_path: Path) -> HistoryEntry:
    return HistoryEntry(
        job_id=job_id,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        old_path_local=str(old_path),
        new_path_local=str(new_path),
        result_path_local=str(result_path),
    )
