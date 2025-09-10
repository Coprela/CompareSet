"""Raster-guided PDF comparison utilities.

This module implements a new diff engine that rasterizes pages only for
comparison and then draws highlight rectangles directly onto the original
vector PDFs. The final output PDFs therefore remain vector based.
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Dict, Iterable, List, Tuple

import fitz  # type: ignore
import numpy as np

try:  # Optional dependency - OpenCV greatly simplifies image operations
    import cv2  # type: ignore
except Exception:  # pragma: no cover - OpenCV may be missing in some envs
    cv2 = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Basic raster utilities
# ---------------------------------------------------------------------------


def rasterize_page(pdf_path: str, page_num: int, dpi: int) -> tuple[np.ndarray, fitz.Rect]:
    """Rasterize ``page_num`` of ``pdf_path`` to a grayscale image.

    The same scaling matrix (``dpi/72``) is used so that multiple calls with the
    same ``dpi`` yield images with identical shapes. The function returns the
    image as a ``numpy`` array and the original page rectangle in PDF points.
    """

    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    with fitz.open(pdf_path) as doc:
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        return arr, page.rect


# ---------------------------------------------------------------------------
# Image alignment
# ---------------------------------------------------------------------------


def _shift_image(img: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Return ``img`` translated by ``dx`` and ``dy`` pixels using empty borders."""

    shifted = np.roll(img, shift=(-dy, -dx), axis=(0, 1))
    if dy > 0:
        shifted[-dy:, :] = 255
    elif dy < 0:
        shifted[:-dy, :] = 255
    if dx > 0:
        shifted[:, -dx:] = 255
    elif dx < 0:
        shifted[:, :-dx] = 255
    return shifted


def align_images(
    imgA: np.ndarray, imgB: np.ndarray
) -> tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """Align ``imgB`` to ``imgA`` and return the aligned images and transform.

    The primary alignment is a translation estimated via phase correlation. If
    OpenCV is available the function also performs a small affine refinement via
    ``cv2.findTransformECC`` allowing minor rotation / scale changes. Returned
    transform parameters are ``dx``, ``dy``, ``rotation`` (degrees) and
    ``scale``.
    """

    if imgA.shape != imgB.shape:
        raise ValueError("Images must have the same shape for alignment")

    # --- phase correlation for translation ---
    fA = np.fft.fft2(imgA)
    fB = np.fft.fft2(imgB)
    R = fA * fB.conj()
    R /= np.abs(R) + 1e-8
    r = np.fft.ifft2(R)
    maxima = np.unravel_index(np.argmax(np.abs(r)), r.shape)
    dy, dx = maxima[0], maxima[1]
    if dy > imgA.shape[0] // 2:
        dy -= imgA.shape[0]
    if dx > imgA.shape[1] // 2:
        dx -= imgA.shape[1]

    alignedB = _shift_image(imgB, dx, dy)
    alignedA = imgA.copy()

    rot = 0.0
    scale = 1.0

    # --- optional affine refinement with OpenCV ---
    if cv2 is not None:
        try:
            warp_mode = cv2.MOTION_AFFINE
            warp_matrix = np.eye(2, 3, dtype=np.float32)
            criteria = (
                cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                50,
                1e-5,
            )
            cc, warp_matrix = cv2.findTransformECC(
                imgA.astype(np.float32),
                alignedB.astype(np.float32),
                warp_matrix,
                warp_mode,
                criteria,
                None,
                1,
            )
            alignedB = cv2.warpAffine(
                alignedB,
                warp_matrix,
                (imgA.shape[1], imgA.shape[0]),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255,
            )
            rot = math.degrees(math.atan2(warp_matrix[0, 1], warp_matrix[0, 0]))
            scale = warp_matrix[0, 0] / math.cos(math.radians(rot))
            dx += warp_matrix[0, 2]
            dy += warp_matrix[1, 2]
        except Exception:  # pragma: no cover - ECC failure falls back to translation
            logger.debug("ECC alignment failed", exc_info=True)

    info = {"dx": float(dx), "dy": float(dy), "rotation": float(rot), "scale": float(scale)}
    return alignedA, alignedB, info


# ---------------------------------------------------------------------------
# Difference detection
# ---------------------------------------------------------------------------


def _iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def _nms(rects: List[Tuple[int, int, int, int]], thr: float) -> List[Tuple[int, int, int, int]]:
    result: List[Tuple[int, int, int, int]] = []
    for r in rects:
        keep = True
        for q in result:
            if _iou(r, q) > thr:
                keep = False
                break
        if keep:
            result.append(r)
    return result


def find_diff_regions(
    imgA: np.ndarray,
    imgB: np.ndarray,
    *,
    method: str = "edges",
    diff_thresh: int = 25,
    dilate_px: int = 3,
    erode_px: int = 1,
    min_area_px: int = 128,
    nms_iou: float = 0.2,
) -> List[Tuple[int, int, int, int]]:
    """Return difference rectangles between ``imgA`` and ``imgB`` in pixels."""

    if cv2 is None:
        raise RuntimeError("OpenCV is required for find_diff_regions")

    if method == "edges":
        edgesA = cv2.Canny(imgA, diff_thresh, diff_thresh * 2)
        edgesB = cv2.Canny(imgB, diff_thresh, diff_thresh * 2)
        if dilate_px > 0:
            k = np.ones((dilate_px, dilate_px), np.uint8)
            edgesA = cv2.dilate(edgesA, k)
            edgesB = cv2.dilate(edgesB, k)
        diff = cv2.bitwise_xor(edgesA, edgesB)
    else:
        diff = cv2.absdiff(imgA, imgB)
        diff = cv2.GaussianBlur(diff, (5, 5), 0)
        _, diff = cv2.threshold(diff, diff_thresh, 255, cv2.THRESH_BINARY)

    if dilate_px > 0:
        diff = cv2.dilate(diff, np.ones((dilate_px, dilate_px), np.uint8))
    if erode_px > 0:
        diff = cv2.erode(diff, np.ones((erode_px, erode_px), np.uint8))

    contours, _ = cv2.findContours(diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects: List[Tuple[int, int, int, int]] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w * h >= min_area_px:
            rects.append((x, y, x + w, y + h))

    return _nms(rects, nms_iou)


# ---------------------------------------------------------------------------
# Conversion utilities
# ---------------------------------------------------------------------------


def px_to_pdf_rects(
    rects_px: List[Tuple[int, int, int, int]],
    dpi: int,
    page_rect_pts: fitz.Rect,
) -> List[fitz.Rect]:
    """Convert pixel rectangles to ``fitz.Rect`` in PDF points.

    ``scale = 72 / dpi`` converts pixel units (from rasterization) to PDF points
    where ``1pt = 1/72`` inch. Because the drawing step works directly on the
    original page, the output PDF remains entirely vector based.
    """

    scale = 72.0 / float(dpi)
    pdf_rects: List[fitz.Rect] = []
    for x0, y0, x1, y1 in rects_px:
        r = fitz.Rect(x0 * scale, y0 * scale, x1 * scale, y1 * scale)
        r.x0 = max(r.x0, page_rect_pts.x0)
        r.y0 = max(r.y0, page_rect_pts.y0)
        r.x1 = min(r.x1, page_rect_pts.x1)
        r.y1 = min(r.y1, page_rect_pts.y1)
        pdf_rects.append(r)
    return pdf_rects


# ---------------------------------------------------------------------------
# Drawing utilities
# ---------------------------------------------------------------------------


def draw_highlight_rects(
    pdf_in_path: str,
    rects_by_page: Dict[int, List[fitz.Rect]],
    color_rgb: Tuple[float, float, float],
    out_path: str,
    *,
    fill_opacity: float = 0.15,
    width: float = 0.8,
) -> None:
    """Draw ``rects_by_page`` onto ``pdf_in_path`` and save ``out_path``."""

    with fitz.open(pdf_in_path) as doc:
        for page_index, rects in rects_by_page.items():
            if page_index >= len(doc):
                continue
            page = doc[page_index]
            for rect in rects:
                page.draw_rect(
                    rect,
                    color=color_rgb,
                    fill=color_rgb,
                    fill_opacity=fill_opacity,
                    width=width,
                )
        doc.save(out_path)


# ---------------------------------------------------------------------------
# High level comparison
# ---------------------------------------------------------------------------


def compare_pdfs_all_pages_raster_guided(
    old_pdf: str,
    new_pdf: str,
    *,
    dpi: int = 300,
    method: str = "edges",
    diff_thresh: int = 25,
    dilate_px: int = 3,
    erode_px: int = 1,
    min_area_px: int = 128,
    nms_iou: float = 0.2,
    ignore_title_block: bool = False,
    ignore_title_rect_pts: Tuple[float, float, float, float] | None = None,
) -> Dict[str, object]:
    """Compare all pages of ``old_pdf`` and ``new_pdf`` using raster guidance."""

    t_start = time.time()
    rects_old: Dict[int, List[Tuple[float, float, float, float]]] = {}
    rects_new: Dict[int, List[Tuple[float, float, float, float]]] = {}
    stats: Dict[int, Dict[str, float]] = {}

    with fitz.open(old_pdf) as doc_old, fitz.open(new_pdf) as doc_new:
        pages = min(len(doc_old), len(doc_new))
        for i in range(pages):
            page_start = time.time()
            try:
                imgA, rectA = rasterize_page(old_pdf, i, dpi)
                imgB, rectB = rasterize_page(new_pdf, i, dpi)
                imgA, imgB, _ = align_images(imgA, imgB)
                rects_px = find_diff_regions(
                    imgA,
                    imgB,
                    method=method,
                    diff_thresh=diff_thresh,
                    dilate_px=dilate_px,
                    erode_px=erode_px,
                    min_area_px=min_area_px,
                    nms_iou=nms_iou,
                )

                # optional ignore region in pixels
                if ignore_title_block and ignore_title_rect_pts:
                    scale = dpi / 72.0
                    x0, y0, x1, y1 = ignore_title_rect_pts
                    mask_rect = (
                        int(x0 * scale),
                        int(y0 * scale),
                        int(x1 * scale),
                        int(y1 * scale),
                    )
                    rects_px = [
                        r
                        for r in rects_px
                        if not (
                            r[0] < mask_rect[2]
                            and r[2] > mask_rect[0]
                            and r[1] < mask_rect[3]
                            and r[3] > mask_rect[1]
                        )
                    ]

                rects_pdf = px_to_pdf_rects(rects_px, dpi, rectA)
                rects_old[i] = [(r.x0, r.y0, r.x1, r.y1) for r in rects_pdf]
                rects_new[i] = [(r.x0, r.y0, r.x1, r.y1) for r in rects_pdf]
                stats[i] = {
                    "count": float(len(rects_pdf)),
                    "area_pts2": float(sum(r.get_area() for r in rects_pdf)),
                }
                logger.info(
                    "page %d processed in %.2fs: %d regions", i, time.time() - page_start, len(rects_pdf)
                )
            except Exception:
                logger.exception("Failed to process page %d", i)
                rects_old[i] = []
                rects_new[i] = []
                stats[i] = {"count": 0.0, "area_pts2": 0.0}

    result: Dict[str, object] = {
        "params": {
            "dpi": dpi,
            "method": method,
            "diff_thresh": diff_thresh,
            "dilate_px": dilate_px,
            "erode_px": erode_px,
            "min_area_px": min_area_px,
            "nms_iou": nms_iou,
            "ignore_title_block": ignore_title_block,
        },
        "pages": pages,
        "rects_old": rects_old,
        "rects_new": rects_new,
        "stats": stats,
        "elapsed": time.time() - t_start,
    }
    return result


def export_marked_pdfs_all_pages(
    old_pdf: str,
    new_pdf: str,
    diff_result: Dict[str, object],
    out_old: str,
    out_new: str,
) -> None:
    """Draw highlighted rectangles for all pages based on ``diff_result``."""

    rects_old_raw = diff_result.get("rects_old", {})
    rects_new_raw = diff_result.get("rects_new", {})
    rects_old = {int(k): [fitz.Rect(r) for r in v] for k, v in rects_old_raw.items()}
    rects_new = {int(k): [fitz.Rect(r) for r in v] for k, v in rects_new_raw.items()}
    draw_highlight_rects(old_pdf, rects_old, (1, 0, 0), out_old)
    draw_highlight_rects(new_pdf, rects_new, (0, 1, 0), out_new)


def save_diff_json(diff_result: Dict[str, object], json_path: str) -> None:
    """Persist ``diff_result`` to ``json_path`` for later inspection."""

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(diff_result, fh, indent=2)


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------


def compare_pdfs_all_pages(
    old_pdf: str,
    new_pdf: str,
    *,
    engine: str = "raster_guided",
    **kwargs,
) -> Dict[str, object]:
    """Facade maintained for compatibility.

    Additional engines can be added in the future. Currently only
    ``"raster_guided"`` is implemented.
    """

    if engine == "raster_guided":
        return compare_pdfs_all_pages_raster_guided(old_pdf, new_pdf, **kwargs)
    raise ValueError(f"Unknown engine: {engine}")


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    import argparse

    parser = argparse.ArgumentParser(description="Raster guided PDF diff")
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument("--out-old", default="old_marked.pdf")
    parser.add_argument("--out-new", default="new_marked.pdf")
    parser.add_argument("--json", default="diff.json")
    args = parser.parse_args()

    diff = compare_pdfs_all_pages_raster_guided(args.old, args.new)
    export_marked_pdfs_all_pages(args.old, args.new, diff, args.out_old, args.out_new)
    save_diff_json(diff, args.json)
