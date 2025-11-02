#!/usr/bin/env python3
"""Compare SET desktop application with enhanced diff suppression."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from importlib import util
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import fitz
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# =============================================================================
# Pipeline configuration (internal constants)
# =============================================================================
DPI = 300
DPI_HIGH = 600
BLUR_KSIZE = 3
THRESH = 28
MORPH_KERNEL = 3
DILATE_ITERS = 2
ERODE_ITERS = 1
MIN_AREA = 36
MIN_DIM = 2
PADDING_PX = 3
PADDING_FRAC = 0.03
VIEW_EXPAND = 1.15
MEAN_DIFF_MIN = 14.0
MEAN_TEXT_DIFF_MIN = 10.0
MIN_FORE_FRACTION = 0.18
EDGE_OVERLAP_MIN = 0.85
ECC_EPS = 1e-5
ECC_ITERS = 1000
STROKE_WIDTH_PT = 0.8
STROKE_OPACITY = 0.6
RED = (1.0, 0.0, 0.0)
GREEN = (0.0, 1.0, 0.0)
DEBUG_DUMPS = False


_ssim_spec = util.find_spec("skimage.metrics")
if _ssim_spec is not None:  # pragma: no cover - optional dependency
    from skimage.metrics import structural_similarity  # type: ignore
else:  # pragma: no cover - optional dependency
    structural_similarity = None  # type: ignore

Rect = Tuple[float, float, float, float]


@dataclass
class Glyph:
    """Representation of a single text glyph in page pixel coordinates."""

    char: str
    bbox: Rect


@dataclass
class PageDiffSummary:
    """Summary of results for a single page pair."""

    index: int
    alignment_method: str
    old_boxes_raw: int
    old_boxes_merged: int
    new_boxes_raw: int
    new_boxes_merged: int


@dataclass
class ComparisonResult:
    """Container for comparison output."""

    pdf_bytes: bytes
    summaries: List[PageDiffSummary] = field(default_factory=list)


class LogEmitter(QObject):
    """Qt signal emitter for log messages."""

    message = Signal(str)


class QtLogHandler(logging.Handler):
    """Logging handler that forwards messages to Qt widgets."""

    def __init__(self, emitter: LogEmitter) -> None:
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        self.emitter.message.emit(message)


class CompareWorker(QObject):
    """Worker object executing the comparison in a background thread."""

    finished = Signal(ComparisonResult)
    failed = Signal(str)

    def __init__(self, old_path: Path, new_path: Path) -> None:
        super().__init__()
        self.old_path = old_path
        self.new_path = new_path

    @Slot()
    def run(self) -> None:
        try:
            result = run_comparison(self.old_path, self.new_path)
        except Exception as exc:  # pragma: no cover - Qt thread
            logger.exception("Comparison failed: %s", exc)
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Compare SET")

        self._log_emitter = LogEmitter()
        self._log_handler = QtLogHandler(self._log_emitter)
        self._log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(self._log_handler)
        self._log_emitter.message.connect(self.append_log)

        self._thread: Optional[QThread] = None
        self._worker: Optional[CompareWorker] = None

        self.old_path_edit = QLineEdit()
        self.new_path_edit = QLineEdit()
        for line_edit in (self.old_path_edit, self.new_path_edit):
            line_edit.setPlaceholderText("Select a PDF file")

        self.old_browse_button = QPushButton("Browse…")
        self.new_browse_button = QPushButton("Browse…")
        self.old_browse_button.clicked.connect(lambda: self.select_file(self.old_path_edit))
        self.new_browse_button.clicked.connect(lambda: self.select_file(self.new_path_edit))

        self.compare_button = QPushButton("Compare")
        self.compare_button.clicked.connect(self.start_comparison)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.status_label = QLabel("Ready")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        file_layout = QGridLayout()
        file_layout.addWidget(QLabel("Old revision (PDF)"), 0, 0)
        file_layout.addWidget(self.old_path_edit, 0, 1)
        file_layout.addWidget(self.old_browse_button, 0, 2)
        file_layout.addWidget(QLabel("New revision (PDF)"), 1, 0)
        file_layout.addWidget(self.new_path_edit, 1, 1)
        file_layout.addWidget(self.new_browse_button, 1, 2)

        main_layout.addLayout(file_layout)
        main_layout.addSpacing(8)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.compare_button)
        main_layout.addLayout(button_layout)

        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.log_view)

        self.setCentralWidget(central_widget)
        self.resize(720, 520)

    @Slot(str)
    def append_log(self, message: str) -> None:
        self.log_view.append(message)
        self.log_view.ensureCursorVisible()

    def select_file(self, target: QLineEdit) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Select PDF", str(Path.home()), "PDF Files (*.pdf)")
        if selected:
            target.setText(selected)

    def start_comparison(self) -> None:
        old_path = Path(self.old_path_edit.text()).expanduser().resolve()
        new_path = Path(self.new_path_edit.text()).expanduser().resolve()

        if not old_path.is_file() or old_path.suffix.lower() != ".pdf":
            QMessageBox.warning(self, "Invalid file", "Please select a valid PDF for the old revision.")
            return
        if not new_path.is_file() or new_path.suffix.lower() != ".pdf":
            QMessageBox.warning(self, "Invalid file", "Please select a valid PDF for the new revision.")
            return

        self.toggle_controls(False)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Comparing…")
        logger.info("Starting comparison: %s vs %s", old_path, new_path)

        self._thread = QThread(self)
        self._worker = CompareWorker(old_path, new_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_comparison_finished)
        self._worker.failed.connect(self.on_comparison_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    @Slot(ComparisonResult)
    def on_comparison_finished(self, result: ComparisonResult) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.toggle_controls(True)
        self.status_label.setText("Comparison complete.")
        logger.info("Comparison finished. Preparing save dialog.")

        default_name = f"CompareSet_Result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Comparison", default_name, "PDF Files (*.pdf)")
        if save_path:
            with open(save_path, "wb") as output_file:
                output_file.write(result.pdf_bytes)
            logger.info("Saved diff to %s", save_path)
            QMessageBox.information(self, "Compare SET", f"Comparison saved to:\n{save_path}")
        else:
            logger.info("Save dialog cancelled by user.")

        self._worker = None
        self._thread = None

    @Slot(str)
    def on_comparison_failed(self, message: str) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.toggle_controls(True)
        self.status_label.setText("Comparison failed.")
        QMessageBox.critical(self, "Compare SET", f"Comparison failed:\n{message}")
        self._worker = None
        self._thread = None

    def toggle_controls(self, enabled: bool) -> None:
        for widget in (
            self.old_browse_button,
            self.new_browse_button,
            self.compare_button,
            self.old_path_edit,
            self.new_path_edit,
        ):
            widget.setEnabled(enabled)


@dataclass
class PageProcessingResult:
    """Detailed results for a processed page pair."""

    alignment_method: str
    old_boxes: List[Rect]
    new_boxes: List[Rect]
    old_raw: int
    new_raw: int


@dataclass
class PageGlyphs:
    """Glyph information for a page pair."""

    old_glyphs: List[Glyph]
    new_glyphs: List[Glyph]


def run_comparison(old_path: Path, new_path: Path) -> ComparisonResult:
    """Execute the raster diff comparison workflow."""

    summaries: List[PageDiffSummary] = []
    output_doc = fitz.open()
    scale = DPI / 72.0

    with fitz.open(old_path) as old_doc, fitz.open(new_path) as new_doc:
        page_pairs = min(old_doc.page_count, new_doc.page_count)
        if page_pairs == 0:
            raise ValueError("No pages available for comparison.")
        if old_doc.page_count != new_doc.page_count:
            logger.warning(
                "Page count mismatch (old=%s, new=%s). Comparing first %s page(s).",
                old_doc.page_count,
                new_doc.page_count,
                page_pairs,
            )

        for index in range(page_pairs):
            result = process_page_pair(old_doc.load_page(index), new_doc.load_page(index))
            if not result.old_boxes and not result.new_boxes:
                logger.info("Page %d alignment: %s", index + 1, result.alignment_method)
                logger.info("Page %d: No diffs detected.", index + 1)
            else:
                logger.info("Page %d alignment: %s", index + 1, result.alignment_method)
                logger.info(
                    "Page %d OLD boxes: raw=%d merged=%d",
                    index + 1,
                    result.old_raw,
                    len(result.old_boxes),
                )
                logger.info(
                    "Page %d NEW boxes: raw=%d merged=%d",
                    index + 1,
                    result.new_raw,
                    len(result.new_boxes),
                )

            base_index = output_doc.page_count
            output_doc.insert_pdf(old_doc, from_page=index, to_page=index)
            output_doc.insert_pdf(new_doc, from_page=index, to_page=index)

            old_page_out = output_doc.load_page(base_index)
            new_page_out = output_doc.load_page(base_index + 1)

            for rect in result.old_boxes:
                pdf_rect = fitz.Rect(rect[0] / scale, rect[1] / scale, rect[2] / scale, rect[3] / scale)
                old_page_out.draw_rect(
                    pdf_rect,
                    color=RED,
                    fill=None,
                    width=STROKE_WIDTH_PT,
                    stroke_opacity=STROKE_OPACITY,
                )
            for rect in result.new_boxes:
                pdf_rect = fitz.Rect(rect[0] / scale, rect[1] / scale, rect[2] / scale, rect[3] / scale)
                new_page_out.draw_rect(
                    pdf_rect,
                    color=GREEN,
                    fill=None,
                    width=STROKE_WIDTH_PT,
                    stroke_opacity=STROKE_OPACITY,
                )

            summaries.append(
                PageDiffSummary(
                    index=index + 1,
                    alignment_method=result.alignment_method,
                    old_boxes_raw=result.old_raw,
                    old_boxes_merged=len(result.old_boxes),
                    new_boxes_raw=result.new_raw,
                    new_boxes_merged=len(result.new_boxes),
                )
            )

    pdf_bytes = output_doc.tobytes()
    output_doc.close()
    logger.info("Generated diff with %d page pair(s).", len(summaries))
    return ComparisonResult(pdf_bytes=pdf_bytes, summaries=summaries)


def process_page_pair(old_page: fitz.Page, new_page: fitz.Page) -> PageProcessingResult:
    """Process a pair of pages and return rectangles for old/new differences."""

    old_high = render_page_to_gray(old_page, DPI_HIGH)
    new_high = render_page_to_gray(new_page, DPI_HIGH)
    aligned_new_high, alignment_method, warp_matrix = align_images(old_high, new_high)

    old_high_blur = cv2.GaussianBlur(old_high, (0, 0), 1.0)
    new_high_blur = cv2.GaussianBlur(aligned_new_high, (0, 0), 1.0)

    old_low = downsample_to_working_resolution(old_high_blur)
    new_low = downsample_to_working_resolution(new_high_blur)

    blur_old = cv2.GaussianBlur(old_low, (BLUR_KSIZE, BLUR_KSIZE), 0)
    blur_new = cv2.GaussianBlur(new_low, (BLUR_KSIZE, BLUR_KSIZE), 0)

    diff = cv2.absdiff(blur_old, blur_new)

    intensity_mask = compute_intensity_mask(diff)
    edge_old, edge_new, edge_mask = compute_edge_mask(blur_old, blur_new)

    change_mask = cv2.bitwise_and(intensity_mask, edge_mask)

    ssim_mask = compute_ssim_mask(blur_old, blur_new)
    if ssim_mask is not None:
        change_mask = cv2.bitwise_and(change_mask, ssim_mask)

    _, old_ink = cv2.threshold(blur_old, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, new_ink = cv2.threshold(blur_new, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    ink_union = cv2.bitwise_or(old_ink, new_ink)
    change_mask = cv2.bitwise_and(change_mask, ink_union)

    glyphs = prepare_page_glyphs(old_page, new_page, warp_matrix)

    old_regions = cv2.bitwise_and(change_mask, old_ink)
    new_regions = cv2.bitwise_and(change_mask, new_ink)

    old_filtered, old_raw = extract_regions(
        old_regions,
        diff,
        old_ink,
        glyphs.old_glyphs,
        glyphs.new_glyphs,
        edge_old,
        edge_new,
    )
    new_filtered, new_raw = extract_regions(
        new_regions,
        diff,
        new_ink,
        glyphs.old_glyphs,
        glyphs.new_glyphs,
        edge_old,
        edge_new,
    )

    old_boxes = merge_rectangles(old_filtered)
    new_boxes = merge_rectangles(new_filtered)

    return PageProcessingResult(
        alignment_method=alignment_method,
        old_boxes=old_boxes,
        new_boxes=new_boxes,
        old_raw=old_raw,
        new_raw=new_raw,
    )


def render_page_to_gray(page: fitz.Page, dpi: int) -> np.ndarray:
    """Render a page to a grayscale numpy array at the requested DPI."""

    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)
    array = np.frombuffer(pix.samples, dtype=np.uint8)
    return array.reshape(pix.height, pix.width)


def align_images(old_img: np.ndarray, new_img: np.ndarray) -> Tuple[np.ndarray, str, np.ndarray]:
    """Align images using ECC with fallbacks, returning the warp matrix."""

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, ECC_ITERS, ECC_EPS)
    old_norm = old_img.astype(np.float32) / 255.0
    new_norm = new_img.astype(np.float32) / 255.0

    for warp_mode, name in ((cv2.MOTION_AFFINE, "affine"), (cv2.MOTION_EUCLIDEAN, "euclidean")):
        warp_matrix = np.eye(2, 3, dtype=np.float32)
        try:
            cv2.findTransformECC(old_norm, new_norm, warp_matrix, warp_mode, criteria)
        except cv2.error:
            continue
        aligned = cv2.warpAffine(
            new_img,
            warp_matrix,
            (old_img.shape[1], old_img.shape[0]),
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_REFLECT,
        )
        return aligned, name, warp_matrix

    shift, _ = cv2.phaseCorrelate(old_norm, new_norm)
    warp_matrix = np.array([[1.0, 0.0, shift[0]], [0.0, 1.0, shift[1]]], dtype=np.float32)
    aligned = cv2.warpAffine(
        new_img,
        warp_matrix,
        (old_img.shape[1], old_img.shape[0]),
        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REFLECT,
    )
    return aligned, "phase_correlation", warp_matrix


def downsample_to_working_resolution(image: np.ndarray) -> np.ndarray:
    """Downsample the high DPI image to the working DPI using area resampling."""

    target_width = int(round(image.shape[1] * (DPI / DPI_HIGH)))
    target_height = int(round(image.shape[0] * (DPI / DPI_HIGH)))
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def compute_intensity_mask(diff: np.ndarray) -> np.ndarray:
    """Compute the intensity-based change mask."""

    _, coarse = cv2.threshold(diff, THRESH, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (MORPH_KERNEL, MORPH_KERNEL))
    coarse = cv2.morphologyEx(coarse, cv2.MORPH_CLOSE, kernel)
    if DILATE_ITERS:
        coarse = cv2.dilate(coarse, kernel, iterations=DILATE_ITERS)
    if ERODE_ITERS:
        coarse = cv2.erode(coarse, kernel, iterations=ERODE_ITERS)
    return coarse


def compute_edge_mask(old_img: np.ndarray, new_img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute edge representations and a mask highlighting structural changes."""

    grad_old_x = cv2.Scharr(old_img, cv2.CV_32F, 1, 0)
    grad_old_y = cv2.Scharr(old_img, cv2.CV_32F, 0, 1)
    grad_new_x = cv2.Scharr(new_img, cv2.CV_32F, 1, 0)
    grad_new_y = cv2.Scharr(new_img, cv2.CV_32F, 0, 1)

    mag_old = cv2.magnitude(grad_old_x, grad_old_y)
    mag_new = cv2.magnitude(grad_new_x, grad_new_y)

    mag_old_u8 = cv2.convertScaleAbs(mag_old)
    mag_new_u8 = cv2.convertScaleAbs(mag_new)

    _, edge_old = cv2.threshold(mag_old_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, edge_new = cv2.threshold(mag_new_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    edge_diff = cv2.absdiff(edge_old, edge_new)
    edge_mask = np.where(edge_diff > 0, 255, 0).astype(np.uint8)
    return edge_old, edge_new, edge_mask


def compute_ssim_mask(old_img: np.ndarray, new_img: np.ndarray) -> Optional[np.ndarray]:
    """Optional SSIM-based refinement mask."""

    if structural_similarity is None:
        return None
    try:
        reduced_old = cv2.resize(old_img, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        reduced_new = cv2.resize(new_img, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        _, ssim_map = structural_similarity(reduced_old, reduced_new, full=True)
    except Exception:  # pragma: no cover - optional dependency runtime errors
        return None

    diff_map = np.clip((1.0 - ssim_map) * 255.0, 0, 255).astype(np.uint8)
    upsampled = cv2.resize(diff_map, (old_img.shape[1], old_img.shape[0]), interpolation=cv2.INTER_LINEAR)
    _, mask = cv2.threshold(upsampled, THRESH, 255, cv2.THRESH_BINARY)
    return mask


def prepare_page_glyphs(old_page: fitz.Page, new_page: fitz.Page, warp_matrix: np.ndarray) -> PageGlyphs:
    """Extract glyphs for both pages and align the new glyphs using the warp matrix."""

    old_glyphs = extract_glyphs(old_page, DPI)
    new_high_glyphs = extract_glyphs(new_page, DPI_HIGH)

    scale_factor = DPI / DPI_HIGH
    aligned_new: List[Glyph] = []
    for glyph in new_high_glyphs:
        transformed = transform_rect(glyph.bbox, warp_matrix)
        scaled = tuple(coord * scale_factor for coord in transformed)
        aligned_new.append(Glyph(glyph.char, scaled))

    return PageGlyphs(old_glyphs=old_glyphs, new_glyphs=aligned_new)


def extract_glyphs(page: fitz.Page, dpi: int) -> List[Glyph]:
    """Extract glyphs from a PDF page at the specified DPI."""

    text = page.get_text("rawdict")
    scale = dpi / 72.0
    glyphs: List[Glyph] = []
    for block in text.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    c = char.get("c")
                    bbox = char.get("bbox")
                    if not c or not bbox:
                        continue
                    x0, y0, x1, y1 = bbox
                    glyphs.append(Glyph(c, (x0 * scale, y0 * scale, x1 * scale, y1 * scale)))
    return glyphs


def transform_rect(rect: Rect, matrix: np.ndarray) -> Rect:
    """Apply an affine transform to a rectangle and return its axis-aligned bounds."""

    points = np.array(
        [
            [rect[0], rect[1], 1.0],
            [rect[2], rect[1], 1.0],
            [rect[0], rect[3], 1.0],
            [rect[2], rect[3], 1.0],
        ],
        dtype=np.float32,
    )
    transformed = (matrix @ points.T).T
    xs = transformed[:, 0]
    ys = transformed[:, 1]
    return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())


def extract_regions(
    mask: np.ndarray,
    diff_img: np.ndarray,
    ink_mask: np.ndarray,
    old_glyphs: Sequence[Glyph],
    new_glyphs: Sequence[Glyph],
    edge_old: np.ndarray,
    edge_new: np.ndarray,
) -> Tuple[List[Rect], int]:
    """Extract filtered bounding boxes from a binary mask."""

    if mask is None or not np.any(mask):
        return [], 0

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    height, width = mask.shape
    rectangles: List[Rect] = []
    pad = max(PADDING_PX, int(min(width, height) * PADDING_FRAC))

    kernel = np.ones((3, 3), np.uint8)

    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area < MIN_AREA:
            continue
        x = stats[label, cv2.CC_STAT_LEFT]
        y = stats[label, cv2.CC_STAT_TOP]
        w_box = stats[label, cv2.CC_STAT_WIDTH]
        h_box = stats[label, cv2.CC_STAT_HEIGHT]
        if w_box < MIN_DIM or h_box < MIN_DIM:
            continue

        component_mask = np.where(labels == label, 255, 0).astype(np.uint8)

        mean_val = cv2.mean(diff_img, mask=component_mask)[0]

        glyph_match = is_identical_text_region(
            (x, y, x + w_box, y + h_box),
            old_glyphs,
            new_glyphs,
            component_mask,
            diff_img,
            edge_old,
            edge_new,
            kernel,
        )
        if glyph_match:
            continue

        if mean_val < MEAN_DIFF_MIN:
            continue

        foreground = cv2.bitwise_and(component_mask, ink_mask)
        if area == 0:
            continue
        fore_fraction = float(cv2.countNonZero(foreground)) / float(area)
        if fore_fraction < MIN_FORE_FRACTION:
            continue

        rect = (
            max(0.0, float(x - pad)),
            max(0.0, float(y - pad)),
            min(float(width), float(x + w_box + pad)),
            min(float(height), float(y + h_box + pad)),
        )
        rectangles.append(apply_view_expand(rect, width, height))

    return rectangles, len(rectangles)


def is_identical_text_region(
    rect: Rect,
    old_glyphs: Sequence[Glyph],
    new_glyphs: Sequence[Glyph],
    component_mask: np.ndarray,
    diff_img: np.ndarray,
    edge_old: np.ndarray,
    edge_new: np.ndarray,
    kernel: np.ndarray,
) -> bool:
    """Return True if the region should be suppressed as stable text."""

    old_text, old_iou = gather_glyph_text(old_glyphs, rect)
    new_text, new_iou = gather_glyph_text(new_glyphs, rect)
    if not old_text or not new_text or old_text != new_text:
        return False
    if old_iou < 0.6 or new_iou < 0.6:
        return False

    eroded = cv2.erode(component_mask, kernel, iterations=1)
    if cv2.countNonZero(eroded) == 0:
        eroded = component_mask
    mean_absdiff = cv2.mean(diff_img, mask=eroded)[0]
    if mean_absdiff >= MEAN_TEXT_DIFF_MIN:
        return False

    overlap = compute_edge_overlap(rect, component_mask, edge_old, edge_new)
    return overlap >= EDGE_OVERLAP_MIN


def gather_glyph_text(glyphs: Sequence[Glyph], rect: Rect) -> Tuple[str, float]:
    """Collect glyphs overlapping a rectangle and compute IoU."""

    x1, y1, x2, y2 = rect
    selected: List[Glyph] = []
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    for glyph in glyphs:
        gx1, gy1, gx2, gy2 = glyph.bbox
        if gx2 <= x1 or gx1 >= x2 or gy2 <= y1 or gy1 >= y2:
            continue
        inter_x1 = max(x1, gx1)
        inter_y1 = max(y1, gy1)
        inter_x2 = min(x2, gx2)
        inter_y2 = min(y2, gy2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            continue
        selected.append(glyph)
        min_x = min(min_x, gx1)
        min_y = min(min_y, gy1)
        max_x = max(max_x, gx2)
        max_y = max(max_y, gy2)

    if not selected:
        return "", 0.0

    bbox = (min_x, min_y, max_x, max_y)
    iou = compute_iou(rect, bbox)

    sorted_glyphs = sorted(selected, key=lambda g: (round(g.bbox[1] / 4.0) * 4.0, g.bbox[0]))
    text = "".join(glyph.char for glyph in sorted_glyphs)
    return text, iou


def compute_iou(a: Rect, b: Rect) -> float:
    """Compute the intersection over union of two rectangles."""

    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0.0:
        return 0.0
    return float(inter_area / union)


def compute_edge_overlap(rect: Rect, component_mask: np.ndarray, edge_old: np.ndarray, edge_new: np.ndarray) -> float:
    """Compute overlap ratio between old/new edge maps inside a region."""

    x1, y1, x2, y2 = [int(round(v)) for v in rect]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(edge_old.shape[1], x2)
    y2 = min(edge_old.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0

    region_mask = component_mask[y1:y2, x1:x2] > 0
    if not np.any(region_mask):
        return 0.0

    old_edges = np.logical_and(edge_old[y1:y2, x1:x2] > 0, region_mask)
    new_edges = np.logical_and(edge_new[y1:y2, x1:x2] > 0, region_mask)

    union = np.logical_or(old_edges, new_edges)
    union_count = int(np.count_nonzero(union))
    if union_count == 0:
        return 0.0
    intersection = int(np.count_nonzero(np.logical_and(old_edges, new_edges)))
    return float(intersection / union_count)


def apply_view_expand(rect: Rect, width: int, height: int) -> Rect:
    """Apply visual padding expansion to a rectangle."""

    x1, y1, x2, y2 = rect
    x1 = max(0.0, float(x1))
    y1 = max(0.0, float(y1))
    x2 = min(float(width), float(x2))
    y2 = min(float(height), float(y2))

    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    half_w = max((x2 - x1) / 2.0, MIN_DIM / 2.0) * VIEW_EXPAND
    half_h = max((y2 - y1) / 2.0, MIN_DIM / 2.0) * VIEW_EXPAND

    expanded_x1 = max(0.0, cx - half_w)
    expanded_y1 = max(0.0, cy - half_h)
    expanded_x2 = min(float(width), cx + half_w)
    expanded_y2 = min(float(height), cy + half_h)

    return (expanded_x1, expanded_y1, expanded_x2, expanded_y2)


def merge_rectangles(rectangles: Sequence[Rect]) -> List[Rect]:
    """Merge overlapping or touching rectangles within a color set."""

    rects = [tuple(rect) for rect in rectangles]
    if not rects:
        return []

    merged: List[Rect] = list(rects)
    changed = True
    while changed:
        changed = False
        next_pass: List[Rect] = []
        while merged:
            current = merged.pop()
            index = 0
            while index < len(merged):
                other = merged[index]
                if rectangles_touch(current, other):
                    current = (
                        min(current[0], other[0]),
                        min(current[1], other[1]),
                        max(current[2], other[2]),
                        max(current[3], other[3]),
                    )
                    merged.pop(index)
                    changed = True
                else:
                    index += 1
            next_pass.append(current)
        merged = next_pass
    merged.reverse()
    return merged


def rectangles_touch(a: Rect, b: Rect) -> bool:
    """Return True if rectangles overlap or touch."""

    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def configure_logging() -> None:
    """Configure root logger for console output."""

    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False


logger = logging.getLogger("compare_set")
configure_logging()


def main() -> None:
    """Entry point for the application."""

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
