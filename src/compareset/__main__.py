"""Command line interface for CompareSet."""
from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Optional

from .compare import RoiMask, compare_pdfs
from .overlay import OverlayOptions, draw_overlays
from .presets import CompareParams, get_preset, parse_color
from .report import write_json_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compareset",
        description="Raster guided PDF comparison with vector overlays.",
    )
    parser.add_argument("--old", required=True, help="Path to the baseline PDF")
    parser.add_argument("--new", required=True, help="Path to the revised PDF")
    parser.add_argument("--out", required=True, help="Output PDF with overlays")
    parser.add_argument("--json", help="Optional JSON diff report path")
    parser.add_argument("--preset", default="balanced", help="Preset name (strict|balanced|loose)")
    parser.add_argument("--dpi", type=int, help="Override raster DPI")
    parser.add_argument("--absdiff-threshold", type=int, help="Absolute difference threshold (0-255)")
    parser.add_argument("--ssim-threshold", type=float, help="SSIM difference threshold (0-1)")
    parser.add_argument("--min-area", type=int, help="Minimum area in pixels")
    parser.add_argument("--padding", type=int, help="Padding in pixels around detections")
    parser.add_argument("--merge-iou", type=float, help="IoU threshold when merging boxes")
    parser.add_argument("--morph-kernel", type=int, help="Morphological kernel size (px)")
    parser.add_argument("--dilate-iterations", type=int, help="Dilate iterations")
    parser.add_argument("--added-threshold", type=int, help="Threshold for additions mask")
    parser.add_argument("--removed-threshold", type=int, help="Threshold for removals mask")
    parser.add_argument(
        "--ignore-roi",
        action="append",
        dest="ignore_rois",
        help="ROI to ignore (format: p<page>:x0,y0,x1,y1 in PDF points)",
    )
    parser.add_argument("--added-color", help="Override color for added regions")
    parser.add_argument("--removed-color", help="Override color for removed regions")
    parser.add_argument("--modified-color", help="Override color for modified regions")
    parser.add_argument("--no-legend", action="store_true", help="Disable legend overlay")
    parser.add_argument("--no-bookmarks", action="store_true", help="Disable bookmarks in output")
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
    colors = preset.colors.with_overrides(
        added=parse_color(args.added_color),
        removed=parse_color(args.removed_color),
        modified=parse_color(args.modified_color),
    )

    try:
        rois = _parse_rois(args.ignore_rois or [])
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    result = compare_pdfs(args.old, args.new, params=params, ignore_rois=rois)

    overlay_opts = OverlayOptions(
        fill_opacity=preset.fill_opacity,
        stroke_width=preset.stroke_width,
        legend=not args.no_legend,
        bookmarks=not args.no_bookmarks,
    )
    draw_overlays(
        result,
        source_pdf=args.new,
        output_pdf=args.out,
        colors=colors,
        options=overlay_opts,
    )

    if args.json:
        write_json_report(result, args.json)

    return 0


def _override_params(preset_params: CompareParams, args: argparse.Namespace) -> CompareParams:
    overrides = {}
    for field_name, arg_name in (
        ("dpi", "dpi"),
        ("absdiff_threshold", "absdiff_threshold"),
        ("ssim_threshold", "ssim_threshold"),
        ("min_area_px", "min_area"),
        ("padding_px", "padding"),
        ("merge_iou", "merge_iou"),
        ("morph_kernel_px", "morph_kernel"),
        ("dilate_iterations", "dilate_iterations"),
        ("added_threshold", "added_threshold"),
        ("removed_threshold", "removed_threshold"),
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
