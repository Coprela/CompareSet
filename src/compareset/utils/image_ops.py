from typing import Tuple, List
import numpy as np

RectPx = Tuple[int, int, int, int]


def align_images(imgA: np.ndarray, imgB: np.ndarray):
    """Return ``imgB`` aligned to ``imgA``.

    The original project relied on OpenCV's phase correlation and affine
    warping.  In this execution environment OpenCV is unavailable, so we use a
    no-op alignment which simply returns the inputs unchanged.  The function
    still reports a zero translation so callers keep working.
    """

    return imgA, imgB, {"dx": 0.0, "dy": 0.0}


def find_diff_regions(
    imgA: np.ndarray,
    imgB: np.ndarray,
    *,
    method: str = "edges",
    diff_thresh: int = 25,
    dilate_px: int = 3,
    erode_px: int = 1,
    min_area_px: int = 128,
) -> List[RectPx]:
    """Return bounding boxes (x0, y0, x1, y1) for differing regions.

    This implementation is intentionally simple and avoids heavy image
    processing dependencies.  Differences are computed via an absolute
    difference followed by a flood fill to group neighbouring pixels into
    rectangular regions.
    """

    # basic absolute difference between images
    diff = np.abs(imgA.astype(np.int16) - imgB.astype(np.int16)) > diff_thresh

    h, w = diff.shape
    visited = np.zeros_like(diff, dtype=bool)
    rects: List[RectPx] = []

    for y in range(h):
        for x in range(w):
            if not diff[y, x] or visited[y, x]:
                continue

            stack = [(y, x)]
            visited[y, x] = True
            min_x = max_x = x
            min_y = max_y = y

            # simple flood fill / connected component labelling
            while stack:
                cy, cx = stack.pop()
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)

                for ny in range(max(cy - 1, 0), min(cy + 2, h)):
                    for nx in range(max(cx - 1, 0), min(cx + 2, w)):
                        if diff[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))

            area = (max_x - min_x + 1) * (max_y - min_y + 1)
            if area >= min_area_px:
                rects.append((min_x, min_y, max_x + 1, max_y + 1))

    return rects


def nms_merge(rects: List[RectPx], iou_thr: float = 0.2) -> List[RectPx]:
    if not rects:
        return rects
    rects_sorted = sorted(rects, key=lambda r: (r[2]-r[0])*(r[3]-r[1]), reverse=True)
    keep: List[RectPx] = []
    while rects_sorted:
        cur = rects_sorted.pop(0)
        keep.append(cur)
        rem = []
        for r in rects_sorted:
            if _iou(cur, r) < iou_thr:
                rem.append(r)
        rects_sorted = rem
    return keep


def _iou(a: RectPx, b: RectPx) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    return inter / float(area_a + area_b - inter)

