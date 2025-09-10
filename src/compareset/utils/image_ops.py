from typing import Tuple, List
import numpy as np
import cv2 as cv

RectPx = Tuple[int,int,int,int]

def align_images(imgA: np.ndarray, imgB: np.ndarray):
    """
    Alinha B -> A (deslocamento; simples e robusto). Pode-se estender com ECC.
    """
    A = imgA.astype(np.float32)
    B = imgB.astype(np.float32)
    A_f = A - A.mean()
    B_f = B - B.mean()
    (dx, dy), _ = cv.phaseCorrelate(np.float32(A_f), np.float32(B_f))
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    B_al = cv.warpAffine(imgB, M, (imgB.shape[1], imgB.shape[0]),
                         flags=cv.INTER_LINEAR, borderMode=cv.BORDER_REPLICATE)
    return imgA, B_al, {"dx": dx, "dy": dy}

def find_diff_regions(imgA: np.ndarray, imgB: np.ndarray, *,
                      method: str = "edges",
                      diff_thresh: int = 25,
                      dilate_px: int = 3,
                      erode_px: int = 1,
                      min_area_px: int = 128) -> List[RectPx]:
    if method == "edges":
        eA = cv.Canny(imgA, 50, 150)
        eB = cv.Canny(imgB, 50, 150)
        eA = cv.dilate(eA, np.ones((3,3), np.uint8), iterations=1)
        eB = cv.dilate(eB, np.ones((3,3), np.uint8), iterations=1)
        diff = cv.absdiff(eA, eB)
    else:
        blurA = cv.GaussianBlur(imgA, (3,3), 0)
        blurB = cv.GaussianBlur(imgB, (3,3), 0)
        diff = cv.absdiff(blurA, blurB)
        _, diff = cv.threshold(diff, diff_thresh, 255, cv.THRESH_BINARY)

    if dilate_px > 0:
        diff = cv.dilate(diff, np.ones((dilate_px, dilate_px), np.uint8), iterations=1)
    if erode_px > 0:
        diff = cv.erode(diff, np.ones((erode_px, erode_px), np.uint8), iterations=1)

    contours, _ = cv.findContours(diff, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    rects: List[RectPx] = []
    for c in contours:
        x,y,w,h = cv.boundingRect(c)
        if w*h >= min_area_px:
            rects.append((x, y, x+w, y+h))
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
    ix0, iy0 = max(ax0,bx0), max(ay0,by0)
    ix1, iy1 = min(ax1,bx1), min(ay1,by1)
    iw, ih = max(0, ix1-ix0), max(0, iy1-iy0)
    inter = iw*ih
    if inter == 0:
        return 0.0
    area_a = (ax1-ax0)*(ay1-ay0)
    area_b = (bx1-bx0)*(by1-by0)
    return inter / float(area_a + area_b - inter)
