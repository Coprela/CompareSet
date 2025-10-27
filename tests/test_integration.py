import json
import os
import subprocess
import sys
from pathlib import Path

import fitz


def _make_pdf(path: Path, rectangles) -> None:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    for rect in rectangles:
        page.draw_rect(fitz.Rect(*rect), color=(0, 0, 0), fill=None)
    doc.save(str(path))
    doc.close()


def run_cli(tmp_path: Path, args):
    cmd = [sys.executable, "-m", "compareset"] + args
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing}" if existing else src_path
    subprocess.run(cmd, check=True, cwd=tmp_path, env=env)


def test_cli_no_diffs(tmp_path):
    old_pdf = tmp_path / "base.pdf"
    new_pdf = tmp_path / "revision.pdf"
    for target in (old_pdf, new_pdf):
        _make_pdf(target, [(40, 40, 140, 140)])
    out_pdf = tmp_path / "out.pdf"
    json_path = tmp_path / "out.json"

    run_cli(
        tmp_path,
        [
            "--old",
            str(old_pdf),
            "--new",
            str(new_pdf),
            "--out",
            str(out_pdf),
            "--json",
            str(json_path),
            "--preset",
            "strict",
            "--dpi",
            "180",
        ],
    )

    assert out_pdf.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["summary"]["total_regions"] == 0


def test_cli_detects_difference(tmp_path):
    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _make_pdf(old_pdf, [(40, 40, 140, 140)])
    _make_pdf(new_pdf, [(40, 40, 140, 140), (120, 120, 170, 170)])

    out_pdf = tmp_path / "result.pdf"
    json_path = tmp_path / "result.json"

    run_cli(
        tmp_path,
        [
            "--old",
            str(old_pdf),
            "--new",
            str(new_pdf),
            "--out",
            str(out_pdf),
            "--json",
            str(json_path),
            "--preset",
            "loose",
            "--dpi",
            "200",
        ],
    )

    assert out_pdf.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["summary"]["total_regions"] >= 1
    assert data["pages"][0]["summary"]["added"] >= 1
