"""Image based PDF comparison pipeline focused on added/removed regions."""
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


@dataclass(frozen=True)
class DiffRegion:
    page_index: int
    bbox_pdf: Tuple[float, float, float, float]
    bbox_px: Tuple[int, int, int, int]
    change_type: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "type": self.change_type,
            "bbox": [float(value) for value in self.bbox_pdf],
            "bbox_px": [int(value) for value in self.bbox_px],
        }


@dataclass(frozen=True)
class PageDiff:
    index: int
    dpi: int
    width_pts: float
    height_pts: float
    regions: List[DiffRegion]
    ssim: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "page_index": self.index,
            "dpi": self.dpi,
            "width_pts": self.width_pts,
            "height_pts": self.height_pts,
            "ssim": self.ssim,
            "regions": [region.to_dict() for region in self.regions],
        }


@dataclass(frozen=True)
class DiffResult:
    params: CompareParams
    pages: List[PageDiff]

    def to_dict(self) -> List[Dict[str, object]]:
        return [page.to_dict() for page in self.pages]


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
        roi_by_page = _index_rois(ignore_rois or ())

        pages: List[PageDiff] = []
        for index in range(page_count):
            page_old = doc_old[index]
            page_new = doc_new[index]
            raster_old = _render_gray(page_old, params.dpi)
            raster_new = _render_gray(page_new, params.dpi)
            if raster_old.shape != raster_new.shape:
                raster_new = _resize_raster(raster_new, raster_old.shape[1], raster_old.shape[0])

            diff_page = _diff_page(
                index=index,
                gray_old=raster_old,
                gray_new=raster_new,
                page_rect=page_new.rect,
                params=params,
                ignore_rois=_iter_rois_for_page(roi_by_page, index),
            )
            pages.append(diff_page)

        return DiffResult(params=params, pages=pages)
    finally:
        doc_old.close()
        doc_new.close()


def _index_rois(rois: Sequence[RoiMask]) -> Dict[int, List[RoiMask]]:
    indexed: Dict[int, List[RoiMask]] = {}
    for roi in rois:
        key = roi.page_index if roi.page_index is not None else -1
        indexed.setdefault(key, []).append(roi)
    return indexed


def _iter_rois_for_page(indexed: Dict[int, List[RoiMask]], page_index: int) -> Iterable[RoiMask]:
    if not indexed:
        return ()
    general = indexed.get(-1, [])
    page_specific = indexed.get(page_index, [])
    return list(general) + list(page_specific)


@dataclass
class _DiffMasks:
    combined: np.ndarray
    added: np.ndarray
    removed: np.ndarray
    ssim_score: float


def _diff_page(
    *,
    index: int,
    gray_old: np.ndarray,
    gray_new: np.ndarray,
    page_rect: fitz.Rect,
    params: CompareParams,
    ignore_rois: Iterable[RoiMask],
) -> PageDiff:
    diff_masks = _compute_diff_masks(gray_old, gray_new, params)
    combined = _apply_morphology(diff_masks.combined, params)

    added_mask = _logical_and(combined, diff_masks.added)
    removed_mask = _logical_and(combined, diff_masks.removed)

    if ignore_rois:
        _apply_roi_masks(added_mask, page_rect, params.dpi, ignore_rois)
        _apply_roi_masks(removed_mask, page_rect, params.dpi, ignore_rois)

    height, width = combined.shape
    added_boxes = _extract_boxes(added_mask, "added")
    removed_boxes = _extract_boxes(removed_mask, "removed")
    merged_boxes = _merge_boxes(added_boxes + removed_boxes, params, width, height)

    regions = _boxes_to_regions(merged_boxes, page_rect, params, index)

    return PageDiff(
        index=index,
        dpi=params.dpi,
        width_pts=page_rect.width,
        height_pts=page_rect.height,
        regions=regions,
        ssim=diff_masks.ssim_score,
    )


def _render_gray(page: fitz.Page, dpi: int) -> np.ndarray:
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _resize_raster(image: np.ndarray, width: int, height: int) -> np.ndarray:
    if image.shape == (height, width):
        return image
    if cv2 is not None:
        interpolation = (
            cv2.INTER_AREA if width < image.shape[1] or height < image.shape[0] else cv2.INTER_LINEAR
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


def _compute_diff_masks(gray_old: np.ndarray, gray_new: np.ndarray, params: CompareParams) -> _DiffMasks:
    if cv2 is not None:
        abs_diff = cv2.absdiff(gray_old, gray_new)
    else:
        abs_diff = np.abs(gray_old.astype(np.int16) - gray_new.astype(np.int16)).astype(np.uint8)
    abs_mask = _threshold(abs_diff, params.absdiff_threshold)

    ssim_score, ssim_map = _compute_ssim(gray_old, gray_new)
    ssim_diff = (1.0 - ssim_map).astype(np.float32)
    ssim_mask = _threshold_float(ssim_diff, params.ssim_threshold)

    ink_old = 255 - gray_old
    ink_new = 255 - gray_new
    added = _positive_difference(ink_new, ink_old)
    removed = _positive_difference(ink_old, ink_new)
    added_mask = _threshold(added, params.added_threshold)
    removed_mask = _threshold(removed, params.removed_threshold)

    combined = np.maximum(abs_mask, ssim_mask)
    combined = np.maximum(combined, np.maximum(added_mask, removed_mask))

    return _DiffMasks(
        combined=combined,
        added=added_mask,
        removed=removed_mask,
        ssim_score=float(ssim_score),
    )


def _compute_ssim(img_a: np.ndarray, img_b: np.ndarray) -> Tuple[float, np.ndarray]:
    if structural_similarity is not None:
        score, ssim_map = structural_similarity(img_a, img_b, full=True)
        return float(score), ssim_map
    diff = np.abs(img_a.astype(np.float32) - img_b.astype(np.float32))
    ssim_map = 1.0 - (diff / 255.0)
    ssim_map = np.clip(ssim_map, 0.0, 1.0)
    return float(ssim_map.mean()), ssim_map


def _threshold(image: np.ndarray, threshold: int) -> np.ndarray:
    mask = (image >= threshold).astype(np.uint8) * 255
    return mask


def _threshold_float(image: np.ndarray, threshold: float) -> np.ndarray:
    mask = (image >= threshold).astype(np.uint8) * 255
    return mask


def _positive_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    diff = a.astype(np.int16) - b.astype(np.int16)
    diff[diff < 0] = 0
    return diff.astype(np.uint8)


def _apply_morphology(mask: np.ndarray, params: CompareParams) -> np.ndarray:
    kernel_size = max(1, int(params.morph_kernel_px))
    if kernel_size % 2 == 0:
        kernel_size += 1
    if cv2 is not None:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        if params.dilate_iterations > 0:
            closed = cv2.dilate(closed, kernel, iterations=params.dilate_iterations)
        return closed
    closed = _binary_close(mask, kernel_size)
    if params.dilate_iterations > 0:
        closed = _binary_dilate(closed, kernel_size, params.dilate_iterations)
    return closed


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


def _logical_and(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.where((a > 0) & (b > 0), 255, 0).astype(np.uint8)


def _apply_roi_masks(mask: np.ndarray, page_rect: fitz.Rect, dpi: int, rois: Iterable[RoiMask]) -> None:
    if mask.size == 0:
        return
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


@dataclass
class _Box:
    x0: int
    y0: int
    x1: int
    y1: int
    change_type: str

    def area(self) -> int:
        return max(0, self.x1 - self.x0) * max(0, self.y1 - self.y0)

    def clip(self, width: int, height: int) -> "_Box":
        return _Box(
            x0=max(0, min(self.x0, width)),
            y0=max(0, min(self.y0, height)),
            x1=max(0, min(self.x1, width)),
            y1=max(0, min(self.y1, height)),
            change_type=self.change_type,
        )

    def union(self, other: "_Box") -> "_Box":
        return _Box(
            x0=min(self.x0, other.x0),
            y0=min(self.y0, other.y0),
            x1=max(self.x1, other.x1),
            y1=max(self.y1, other.y1),
            change_type=self.change_type,
        )

    def expanded(self, padding: int, width: int, height: int) -> "_Box":
        return _Box(
            x0=max(0, self.x0 - padding),
            y0=max(0, self.y0 - padding),
            x1=min(width, self.x1 + padding),
            y1=min(height, self.y1 + padding),
            change_type=self.change_type,
        )


def _extract_boxes(mask: np.ndarray, change_type: str) -> List[_Box]:
    if mask.size == 0:
        return []
    if cv2 is not None:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: List[_Box] = []
        for contour in contours:
            if len(contour) == 0:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w <= 0 or h <= 0:
                continue
            boxes.append(_Box(x, y, x + w, y + h, change_type))
        return boxes
    return _connected_components(mask, change_type)


def _connected_components(mask: np.ndarray, change_type: str) -> List[_Box]:
    binary = mask > 0
    height, width = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    boxes: List[_Box] = []
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
            boxes.append(_Box(min_x, min_y, max_x + 1, max_y + 1, change_type))
    return boxes


def _merge_boxes(boxes: List[_Box], params: CompareParams, width: int, height: int) -> List[_Box]:
    boxes = [box.clip(width, height) for box in boxes if box.area() > 0]
    if not boxes:
        return []

    changed = True
    while changed:
        changed = False
        boxes.sort(key=lambda b: (b.change_type, b.y0, b.x0))
        idx = 0
        while idx < len(boxes):
            base = boxes[idx]
            j = idx + 1
            while j < len(boxes):
                other = boxes[j]
                if base.change_type != other.change_type:
                    j += 1
                    continue
                decision = _merge_decision(base, other, params, width, height)
                if decision == "drop_other":
                    boxes.pop(j)
                    changed = True
                    continue
                if decision == "replace_base":
                    boxes[idx] = other
                    boxes.pop(j)
                    base = other
                    changed = True
                    continue
                if decision == "merge":
                    base = base.union(other).clip(width, height)
                    boxes[idx] = base
                    boxes.pop(j)
                    changed = True
                    continue
                j += 1
            idx += 1

    boxes = _nms(boxes, 0.9)
    return [box for box in boxes if box.area() >= params.min_box_area_px]


def _merge_decision(
    base: _Box,
    other: _Box,
    params: CompareParams,
    width: int,
    height: int,
) -> str:
    expanded_base = base.expanded(params.padding_px, width, height)
    expanded_other = other.expanded(params.padding_px, width, height)

    if _contains(expanded_base, expanded_other, params.contain_eps_px):
        if base.area() >= other.area():
            return "drop_other"
        return "replace_base"
    if _contains(expanded_other, expanded_base, params.contain_eps_px):
        if base.area() >= other.area():
            return "replace_base"
        return "drop_other"

    if _iou(expanded_base, expanded_other) >= params.merge_iou:
        return "merge"
    if _edge_distance(expanded_base, expanded_other) <= params.touch_gap_px:
        return "merge"
    return "none"


def _contains(container: _Box, candidate: _Box, eps: int) -> bool:
    return (
        candidate.x0 >= container.x0 - eps
        and candidate.y0 >= container.y0 - eps
        and candidate.x1 <= container.x1 + eps
        and candidate.y1 <= container.y1 + eps
    )


def _edge_distance(a: _Box, b: _Box) -> float:
    if _iou(a, b) > 0.0:
        return 0.0
    if a.x1 < b.x0:
        gap_x = b.x0 - a.x1
    elif b.x1 < a.x0:
        gap_x = a.x0 - b.x1
    else:
        gap_x = 0.0
    if a.y1 < b.y0:
        gap_y = b.y0 - a.y1
    elif b.y1 < a.y0:
        gap_y = a.y0 - b.y1
    else:
        gap_y = 0.0
    return float(math.hypot(gap_x, gap_y))


def _iou(a: _Box, b: _Box) -> float:
    inter_x0 = max(a.x0, b.x0)
    inter_y0 = max(a.y0, b.y0)
    inter_x1 = min(a.x1, b.x1)
    inter_y1 = min(a.y1, b.y1)
    iw = max(0, inter_x1 - inter_x0)
    ih = max(0, inter_y1 - inter_y0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = a.area()
    area_b = b.area()
    denom = float(area_a + area_b - inter)
    if denom <= 0:
        return 0.0
    return inter / denom


def _nms(boxes: List[_Box], threshold: float) -> List[_Box]:
    if not boxes:
        return []
    boxes_sorted = sorted(boxes, key=lambda b: (b.change_type, -b.area()))
    kept: List[_Box] = []
    for box in boxes_sorted:
        should_keep = True
        for other in kept:
            if box.change_type != other.change_type:
                continue
            if _iou(box, other) >= threshold:
                should_keep = False
                break
        if should_keep:
            kept.append(box)
    return kept


def _boxes_to_regions(
    boxes: List[_Box],
    page_rect: fitz.Rect,
    params: CompareParams,
    page_index: int,
) -> List[DiffRegion]:
    if not boxes:
        return []
    scale = 72.0 / params.dpi
    regions: List[DiffRegion] = []
    for box in boxes:
        pdf_rect = (
            page_rect.x0 + box.x0 * scale,
            page_rect.y0 + box.y0 * scale,
            page_rect.x0 + box.x1 * scale,
            page_rect.y0 + box.y1 * scale,
        )
        regions.append(
            DiffRegion(
                page_index=page_index,
                bbox_pdf=pdf_rect,
                bbox_px=(box.x0, box.y0, box.x1, box.y1),
                change_type=box.change_type,
            )
        )
    regions.sort(key=lambda region: (region.change_type, region.bbox_pdf))
    return regions
