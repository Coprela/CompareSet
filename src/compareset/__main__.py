"""Command line interface for CompareSet."""
from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Optional

from .compare import RoiMask, compare_pdfs
from .overlay import annotate_pdf, make_annotation_style
from .presets import CompareParams, get_preset
from .report import write_json_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compareset",
        description="Raster guided PDF comparison with vector overlays.",
    )
    parser.add_argument("--old", required=True, help="Path to the baseline PDF")
    parser.add_argument("--new", required=True, help="Path to the revised PDF")
    parser.add_argument("--old-annotated", required=True, help="Output PDF for removed regions")
    parser.add_argument("--new-annotated", required=True, help="Output PDF for added regions")
    parser.add_argument("--json", required=True, help="Diff report path (JSON)")
    parser.add_argument("--preset", default="balanced", help="Preset name (strict|balanced|loose)")
    parser.add_argument("--dpi", type=int, help="Override raster DPI")
    parser.add_argument("--absdiff-threshold", type=int, help="Absolute difference threshold (0-255)")
    parser.add_argument("--ssim-threshold", type=float, help="SSIM difference threshold (0-1)")
    parser.add_argument("--morph-kernel", type=int, help="Morphological kernel size (px)")
    parser.add_argument("--dilate-iterations", type=int, help="Dilate iterations")
    parser.add_argument("--merge-iou", type=float, help="IoU threshold when merging boxes")
    parser.add_argument("--touch-gap-px", type=int, help="Maximum gap for touching boxes")
    parser.add_argument("--contain-eps-px", type=int, help="Containment tolerance in pixels")
    parser.add_argument("--padding", type=int, help="Padding in pixels applied before merging")
    parser.add_argument("--min-box-area", type=int, help="Minimum area (px^2) after merging")
    parser.add_argument("--added-threshold", type=int, help="Threshold for additions mask")
    parser.add_argument("--removed-threshold", type=int, help="Threshold for removals mask")
    parser.add_argument(
        "--ignore-roi",
        action="append",
        dest="ignore_rois",
        help="ROI to ignore (format: p<page>:x0,y0,x1,y1 in PDF points)",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from . import __version__  # type: ignore[attr-defined]

        print(__version__)
        return 0

    try:
        preset = get_preset(args.preset)
    except KeyError as exc:
        parser.error(str(exc))
        return 2

    params = _override_params(preset.params, args)
    try:
        rois = _parse_rois(args.ignore_rois or [])
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    result = compare_pdfs(args.old, args.new, params=params, ignore_rois=rois)

    removed_style = make_annotation_style(
        preset.colors.removed,
        stroke_width=preset.stroke_width,
        fill_opacity=preset.fill_opacity,
    )
    added_style = make_annotation_style(
        preset.colors.added,
        stroke_width=preset.stroke_width,
        fill_opacity=preset.fill_opacity,
    )

    annotate_pdf(
        result,
        source_pdf=args.old,
        output_pdf=args.old_annotated,
        change_type="removed",
        style=removed_style,
    )
    annotate_pdf(
        result,
        source_pdf=args.new,
        output_pdf=args.new_annotated,
        change_type="added",
        style=added_style,
    )

    write_json_report(result, args.json)

    return 0


def _override_params(preset_params: CompareParams, args: argparse.Namespace) -> CompareParams:
    overrides = {}
    for field_name, arg_name in (
        ("dpi", "dpi"),
        ("absdiff_threshold", "absdiff_threshold"),
        ("ssim_threshold", "ssim_threshold"),
        ("morph_kernel_px", "morph_kernel"),
        ("dilate_iterations", "dilate_iterations"),
        ("added_threshold", "added_threshold"),
        ("removed_threshold", "removed_threshold"),
        ("merge_iou", "merge_iou"),
        ("touch_gap_px", "touch_gap_px"),
        ("contain_eps_px", "contain_eps_px"),
        ("padding_px", "padding"),
        ("min_box_area_px", "min_box_area"),
    ):
        value = getattr(args, arg_name)
        if value is not None:
            overrides[field_name] = value
    return preset_params.copy(**overrides)


def _parse_rois(values: List[str]) -> List[RoiMask]:
    rois: List[RoiMask] = []
    for value in values:
        value = value.strip()
        if not value:
            continue
        page_index = None
        coords = value
        if value.lower().startswith("p") and ":" in value:
            prefix, coords = value.split(":", 1)
            try:
                page_index = int(prefix[1:]) - 1
            except ValueError as exc:
                raise ValueError(f"Invalid ROI page specifier '{prefix}'") from exc
            if page_index < 0:
                page_index = 0
        parts = [c.strip() for c in coords.split(",")]
        if len(parts) != 4:
            raise ValueError(f"ROI '{value}' must have four coordinates")
        try:
            rect = tuple(float(p) for p in parts)  # type: ignore[assignment]
        except ValueError as exc:
            raise ValueError(f"ROI '{value}' has invalid coordinates") from exc
        x0, y0, x1, y1 = rect
        rect_sorted = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        rois.append(RoiMask(page_index=page_index, rect_pts=rect_sorted))
    return rois


if __name__ == "__main__":
    sys.exit(main())
