"""JSON report helpers."""
from __future__ import annotations

import json
from pathlib import Path
from .compare import DiffResult


def write_json_report(result: DiffResult, path: str | Path) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = result.to_dict()
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def diff_result_to_json(result: DiffResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
