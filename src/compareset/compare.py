"""Core raster comparison orchestrator."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import fitz
import numpy as np

try:  # pragma: no cover - optional dependency
    import cv2  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from skimage.metrics import structural_similarity  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    structural_similarity = None  # type: ignore

from .presets import CompareParams


@dataclass(frozen=True)
class RoiMask:
    """Region (in PDF points) to ignore while diffing."""

    page_index: Optional[int]
    rect_pts: Tuple[float, float, float, float]


@dataclass
class DiffRegion:
    page_index: int
    bbox_pdf: Tuple[float, float, float, float]
    bbox_px: Tuple[int, int, int, int]
    change_type: str
    score: float
    area_pts2: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "page": self.page_index,
            "bbox_pdf": list(self.bbox_pdf),
            "bbox_px": list(self.bbox_px),
            "type": self.change_type,
            "score": self.score,
            "area_pts2": self.area_pts2,
        }


@dataclass
class PageDiff:
    index: int
    width_pts: float
    height_pts: float
    regions: List[DiffRegion]
    ssim: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "index": self.index,
            "width_pts": self.width_pts,
            "height_pts": self.height_pts,
            "ssim": self.ssim,
            "regions": [r.to_dict() for r in self.regions],
            "summary": {
                "total": len(self.regions),
                "added": sum(1 for r in self.regions if r.change_type == "added"),
                "removed": sum(1 for r in self.regions if r.change_type == "removed"),
                "modified": sum(1 for r in self.regions if r.change_type == "modified"),
            },
        }


@dataclass
class DiffResult:
    params: CompareParams
    pages: List[PageDiff]
    extra_pages_old: int
    extra_pages_new: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "params": self.params.to_dict(),
            "pages": [p.to_dict() for p in self.pages],
            "extra_pages_old": self.extra_pages_old,
            "extra_pages_new": self.extra_pages_new,
            "summary": {
                "total_regions": sum(len(p.regions) for p in self.pages),
                "pages_with_regions": sum(1 for p in self.pages if p.regions),
            },
        }


def compare_pdfs(
    old_pdf: str | Path,
    new_pdf: str | Path,
    *,
    params: CompareParams,
    ignore_rois: Sequence[RoiMask] | None = None,
) -> DiffResult:
    doc_old = fitz.open(str(old_pdf))
    doc_new = fitz.open(str(new_pdf))
    try:
        page_count = min(len(doc_old), len(doc_new))
        roi_by_page = _index_rois(ignore_rois)

        pages: List[PageDiff] = []
        for index in range(page_count):
            page_old = doc_old[index]
            page_new = doc_new[index]
            gray_old = _render_gray(page_old, params.dpi)
            gray_new = _render_gray(page_new, params.dpi)
            if gray_old.shape != gray_new.shape:
                gray_old = _resize_raster(gray_old, gray_new.shape[1], gray_new.shape[0])

            page_result = _diff_page(
                index=index,
                gray_old=gray_old,
                gray_new=gray_new,
                page_rect=page_new.rect,
                params=params,
                ignore_rois=_iter_rois_for_page(roi_by_page, index),
            )
            pages.append(page_result)

        return DiffResult(
            params=params,
            pages=pages,
            extra_pages_old=max(0, len(doc_old) - page_count),
            extra_pages_new=max(0, len(doc_new) - page_count),
        )
    finally:
        doc_old.close()
        doc_new.close()


def _index_rois(rois: Optional[Sequence[RoiMask]]) -> Dict[int, List[RoiMask]]:
    indexed: Dict[int, List[RoiMask]] = {}
    if not rois:
        return indexed
    for roi in rois:
        if roi.page_index is None:
            indexed.setdefault(-1, []).append(roi)
        else:
            indexed.setdefault(roi.page_index, []).append(roi)
    return indexed


def _iter_rois_for_page(indexed: Dict[int, List[RoiMask]], page_index: int) -> Iterable[RoiMask]:
    if not indexed:
        return ()
    rois = list(indexed.get(-1, ()))
    rois.extend(indexed.get(page_index, ()))
    return rois


def _render_gray(page: fitz.Page, dpi: int) -> np.ndarray:
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return arr


def _resize_raster(image: np.ndarray, width: int, height: int) -> np.ndarray:
    if image.shape == (height, width):
        return image
    if cv2 is not None:
        interpolation = (
            cv2.INTER_AREA
            if width < image.shape[1] or height < image.shape[0]
            else cv2.INTER_LINEAR
        )
        return cv2.resize(image, (width, height), interpolation=interpolation)

    src_height, src_width = image.shape
    if src_height == 0 or src_width == 0:
        return image

    y_idx = np.linspace(0, src_height - 1, height)
    x_idx = np.linspace(0, src_width - 1, width)
    y_idx = np.clip(np.round(y_idx).astype(int), 0, src_height - 1)
    x_idx = np.clip(np.round(x_idx).astype(int), 0, src_width - 1)
    return image[np.ix_(y_idx, x_idx)]


def _diff_page(
    *,
    index: int,
    gray_old: np.ndarray,
    gray_new: np.ndarray,
    page_rect: fitz.Rect,
    params: CompareParams,
    ignore_rois: Iterable[RoiMask],
) -> PageDiff:
    abs_mask = _threshold(np.abs(gray_old.astype(np.int16) - gray_new.astype(np.int16)), params.absdiff_threshold)

    ssim_score, ssim_map = _compute_ssim(gray_old, gray_new)
    ssim_diff = (1.0 - ssim_map).astype(np.float32)
    ssim_mask = (ssim_diff >= params.ssim_threshold).astype(np.uint8) * 255

    added = _positive_difference(gray_old, gray_new)
    removed = _positive_difference(gray_new, gray_old)
    added_mask = _threshold(added, params.added_threshold)
    removed_mask = _threshold(removed, params.removed_threshold)

    combined = np.maximum(np.maximum(abs_mask, ssim_mask), np.maximum(added_mask, removed_mask))

    combined = _apply_morphology(combined, params.morph_kernel_px, params.dilate_iterations)

    combined = _apply_roi_masks(
        combined, page_rect, params.dpi, ignore_rois, extra_masks=(added_mask, removed_mask)
    )

    boxes = _find_candidate_boxes(combined, params.min_area_px)
    regions = _boxes_to_regions(
        boxes=boxes,
        combined=combined,
        added_mask=added_mask,
        removed_mask=removed_mask,
        page_rect=page_rect,
        params=params,
        page_index=index,
    )

    return PageDiff(
        index=index,
        width_pts=page_rect.width,
        height_pts=page_rect.height,
        regions=regions,
        ssim=float(ssim_score),
    )


def _apply_roi_masks(
    mask: np.ndarray,
    page_rect: fitz.Rect,
    dpi: int,
    rois: Iterable[RoiMask],
    *,
    extra_masks: Tuple[np.ndarray, np.ndarray],
) -> np.ndarray:
    if not rois:
        return mask
    added_mask, removed_mask = extra_masks
    scale = dpi / 72.0
    height, width = mask.shape
    for roi in rois:
        x0, y0, x1, y1 = roi.rect_pts
        px0 = int(max(0, math.floor((x0 - page_rect.x0) * scale)))
        py0 = int(max(0, math.floor((y0 - page_rect.y0) * scale)))
        px1 = int(min(width, math.ceil((x1 - page_rect.x0) * scale)))
        py1 = int(min(height, math.ceil((y1 - page_rect.y0) * scale)))
        if px0 >= px1 or py0 >= py1:
            continue
        mask[py0:py1, px0:px1] = 0
        added_mask[py0:py1, px0:px1] = 0
        removed_mask[py0:py1, px0:px1] = 0
    return mask


def _boxes_to_regions(
    *,
    boxes: Sequence[Tuple[int, int, int, int]],
    combined: np.ndarray,
    added_mask: np.ndarray,
    removed_mask: np.ndarray,
    page_rect: fitz.Rect,
    params: CompareParams,
    page_index: int,
) -> List[DiffRegion]:
    height, width = combined.shape
    enriched: List[Tuple[int, int, int, int, float, float, str]] = []
    scale = 72.0 / params.dpi
    for (x0_raw, y0_raw, x1_raw, y1_raw) in boxes:
        w = x1_raw - x0_raw
        h = y1_raw - y0_raw
        if w * h < params.min_area_px:
            continue
        x0 = max(0, x0_raw - params.padding_px)
        y0 = max(0, y0_raw - params.padding_px)
        x1 = min(width, x1_raw + params.padding_px)
        y1 = min(height, y1_raw + params.padding_px)

        crop = combined[y0:y1, x0:x1]
        added_crop = added_mask[y0:y1, x0:x1]
        removed_crop = removed_mask[y0:y1, x0:x1]

        added_score = float(added_crop.mean() / 255.0) if added_crop.size else 0.0
        removed_score = float(removed_crop.mean() / 255.0) if removed_crop.size else 0.0
        change_type = _classify_region(added_score, removed_score)
        score = float(crop.mean() / 255.0) if crop.size else 0.0

        diff_score = added_score - removed_score
        enriched.append((x0, y0, x1, y1, score, diff_score, change_type))

    enriched = _merge_boxes(enriched, params.merge_iou)

    regions: List[DiffRegion] = []
    for x0, y0, x1, y1, score, diff_score, change_type in enriched:
        resolved_type = _resolve_change_type(diff_score, change_type)
        pdf_rect = (
            page_rect.x0 + x0 * scale,
            page_rect.y0 + y0 * scale,
            page_rect.x0 + x1 * scale,
            page_rect.y0 + y1 * scale,
        )
        area_pts = (pdf_rect[2] - pdf_rect[0]) * (pdf_rect[3] - pdf_rect[1])
        regions.append(
            DiffRegion(
                page_index=page_index,
                bbox_pdf=pdf_rect,
                bbox_px=(x0, y0, x1, y1),
                change_type=resolved_type,
                score=score,
                area_pts2=float(area_pts),
            )
        )
    regions.sort(key=lambda r: (r.change_type, r.bbox_pdf))
    return regions


def _classify_region(added_score: float, removed_score: float) -> str:
    threshold = 0.05
    added_active = added_score >= threshold
    removed_active = removed_score >= threshold
    if added_active and not removed_active:
        return "added"
    if removed_active and not added_active:
        return "removed"
    return "modified"


def _resolve_change_type(diff_score: float, default_type: str) -> str:
    if diff_score > 0.05:
        return "added"
    if diff_score < -0.05:
        return "removed"
    return default_type


def _threshold(image: np.ndarray, threshold: int) -> np.ndarray:
    mask = (image >= threshold).astype(np.uint8) * 255
    return mask


def _positive_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    diff = a.astype(np.int16) - b.astype(np.int16)
    diff[diff < 0] = 0
    return diff.astype(np.uint8)


def _apply_morphology(mask: np.ndarray, kernel_size: int, dilate_iterations: int) -> np.ndarray:
    kernel_size = max(1, int(kernel_size))
    if kernel_size % 2 == 0:
        kernel_size += 1
    if cv2 is not None:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        if dilate_iterations > 0:
            mask = cv2.dilate(mask, kernel, iterations=dilate_iterations)
        return mask
    mask = _binary_close(mask, kernel_size)
    if dilate_iterations > 0:
        mask = _binary_dilate(mask, kernel_size, dilate_iterations)
    return mask


def _find_candidate_boxes(mask: np.ndarray, min_area_px: int) -> List[Tuple[int, int, int, int]]:
    if cv2 is not None:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: List[Tuple[int, int, int, int]] = []
        for contour in contours:
            if len(contour) == 0:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w * h >= min_area_px:
                boxes.append((x, y, x + w, y + h))
        return boxes
    return _connected_components(mask, min_area_px)


def _connected_components(mask: np.ndarray, min_area_px: int) -> List[Tuple[int, int, int, int]]:
    binary = mask > 0
    height, width = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    boxes: List[Tuple[int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            if not binary[y, x] or visited[y, x]:
                continue
            stack = [(y, x)]
            visited[y, x] = True
            min_x = max_x = x
            min_y = max_y = y
            while stack:
                cy, cx = stack.pop()
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for ny in range(max(cy - 1, 0), min(cy + 2, height)):
                    for nx in range(max(cx - 1, 0), min(cx + 2, width)):
                        if binary[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
            area = (max_x - min_x + 1) * (max_y - min_y + 1)
            if area >= min_area_px:
                boxes.append((min_x, min_y, max_x + 1, max_y + 1))
    return boxes


def _binary_close(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    return _binary_erode(_binary_dilate(mask, kernel_size, 1), kernel_size, 1)


def _binary_dilate(mask: np.ndarray, kernel_size: int, iterations: int) -> np.ndarray:
    result = mask.copy()
    for _ in range(iterations):
        result = _max_filter(result, kernel_size)
    return result


def _binary_erode(mask: np.ndarray, kernel_size: int, iterations: int) -> np.ndarray:
    result = mask.copy()
    for _ in range(iterations):
        result = _min_filter(result, kernel_size)
    return result


def _max_filter(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    pad = kernel_size // 2
    padded = np.pad(mask, pad, mode="constant", constant_values=0)
    h, w = mask.shape
    out = np.zeros_like(mask)
    for dy in range(kernel_size):
        for dx in range(kernel_size):
            out = np.maximum(out, padded[dy : dy + h, dx : dx + w])
    return out


def _min_filter(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    pad = kernel_size // 2
    padded = np.pad(mask, pad, mode="constant", constant_values=255)
    h, w = mask.shape
    out = np.full_like(mask, 255)
    for dy in range(kernel_size):
        for dx in range(kernel_size):
            out = np.minimum(out, padded[dy : dy + h, dx : dx + w])
    return out


def _compute_ssim(img_a: np.ndarray, img_b: np.ndarray) -> Tuple[float, np.ndarray]:
    if structural_similarity is not None:
        score, ssim_map = structural_similarity(img_a, img_b, full=True)
        return float(score), ssim_map
    diff = np.abs(img_a.astype(np.float32) - img_b.astype(np.float32))
    ssim_map = 1.0 - (diff / 255.0)
    ssim_map = np.clip(ssim_map, 0.0, 1.0)
    score = float(ssim_map.mean())
    return score, ssim_map


def _merge_boxes(
    boxes: Sequence[Tuple[int, int, int, int, float, float, str]],
    merge_iou: float,
) -> List[Tuple[int, int, int, int, float, float, str]]:
    if merge_iou <= 0 or len(boxes) <= 1:
        return list(boxes)
    remaining = sorted(boxes, key=lambda item: (item[0], item[1]))
    merged: List[Tuple[int, int, int, int, float, float, str]] = []
    while remaining:
        base = remaining.pop(0)
        bx0, by0, bx1, by1, bscore, diff_score, change_type = base
        overlaps: List[int] = []
        for idx, other in enumerate(remaining):
            if _iou(base, other) >= merge_iou:
                ox0, oy0, ox1, oy1, oscore, odiff, otype = other
                bx0 = min(bx0, ox0)
                by0 = min(by0, oy0)
                bx1 = max(bx1, ox1)
                by1 = max(by1, oy1)
                bscore = max(bscore, oscore)
                diff_score += odiff
                change_type = _merge_change_type(change_type, otype)
                overlaps.append(idx)
        for offset, idx in enumerate(overlaps):
            remaining.pop(idx - offset)
        merged.append((bx0, by0, bx1, by1, bscore, diff_score, change_type))
    return merged


def _merge_change_type(a: str, b: str) -> str:
    if a == b:
        return a
    if "modified" in (a, b):
        return "modified"
    return "modified"


def _iou(
    a: Tuple[int, int, int, int, float, float, str],
    b: Tuple[int, int, int, int, float, float, str],
) -> float:
    ax0, ay0, ax1, ay1 = a[:4]
    bx0, by0, bx1, by1 = b[:4]
    inter_x0 = max(ax0, bx0)
    inter_y0 = max(ay0, by0)
    inter_x1 = min(ax1, bx1)
    inter_y1 = min(ay1, by1)
    iw = max(0, inter_x1 - inter_x0)
    ih = max(0, inter_y1 - inter_y0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    denom = float(area_a + area_b - inter)
    if denom <= 0:
        return 0.0
    return inter / denom
