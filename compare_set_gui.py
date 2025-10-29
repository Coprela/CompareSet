"""
REQUIREMENTS:
PySide6
pymupdf
opencv-python
numpy
"""

import os
import sys
import traceback
from datetime import datetime
from typing import Callable, List, Optional, Sequence, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QTextEdit,
    QWidget,
)


DPI = 300
BLUR_KSIZE = 3
THRESH = 25
MORPH_KERNEL = 3
DILATE_ITERS = 2
ERODE_ITERS = 1
MIN_AREA = 36
MIN_DIM = 2
PADDING_PX = 3
PADDING_FRAC = 0.03
MEAN_DIFF_MIN = 12.0
MIN_FORE_FRACTION = 0.15
STROKE_WIDTH_PT = 0.8
STROKE_OPACITY = 0.6
RED = (1.0, 0.0, 0.0)
GREEN = (0.0, 1.0, 0.0)

PIXEL_TO_POINT = 72.0 / DPI


Rect = Tuple[int, int, int, int]


def _ensure_grayscale_pixmap(page: fitz.Page) -> Tuple[np.ndarray, int, int]:
    scale = DPI / 72.0
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return arr, pix.width, pix.height


def _center_on_canvas(image: np.ndarray, canvas_shape: Tuple[int, int]) -> Tuple[np.ndarray, Tuple[int, int]]:
    canvas_h, canvas_w = canvas_shape
    img_h, img_w = image.shape
    canvas = np.full((canvas_h, canvas_w), 255, dtype=np.uint8)
    y_offset = (canvas_h - img_h) // 2
    x_offset = (canvas_w - img_w) // 2
    canvas[y_offset : y_offset + img_h, x_offset : x_offset + img_w] = image
    return canvas, (x_offset, y_offset)


def _find_candidate_boxes(
    mask: np.ndarray,
    ink_mask: np.ndarray,
    diff: np.ndarray,
    canvas_shape: Tuple[int, int],
) -> List[Rect]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: List[Rect] = []
    canvas_h, canvas_w = canvas_shape
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_AREA:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            continue
        pad = max(PADDING_PX, int(min(w, h) * PADDING_FRAC))
        x_pad = max(0, x - pad)
        y_pad = max(0, y - pad)
        x2_pad = min(canvas_w, x + w + pad)
        y2_pad = min(canvas_h, y + h + pad)
        if x2_pad <= x_pad or y2_pad <= y_pad:
            continue
        if (x2_pad - x_pad) < MIN_DIM or (y2_pad - y_pad) < MIN_DIM:
            continue
        diff_region = diff[y : y + h, x : x + w]
        if diff_region.size == 0:
            continue
        mean_diff = float(np.mean(diff_region))
        if mean_diff < MEAN_DIFF_MIN:
            continue
        ink_region = ink_mask[y : y + h, x : x + w]
        if ink_region.size == 0:
            continue
        foreground_fraction = float(np.count_nonzero(ink_region)) / float(w * h)
        if foreground_fraction < MIN_FORE_FRACTION:
            continue
        boxes.append((x_pad, y_pad, x2_pad, y2_pad))
    return boxes


def _boxes_touch_or_overlap(a: Rect, b: Rect) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    horizontal = not (ax2 < bx1 or bx2 < ax1)
    vertical = not (ay2 < by1 or by2 < ay1)
    return horizontal and vertical


def _merge_boxes(boxes: Sequence[Rect]) -> List[Rect]:
    if not boxes:
        return []
    working = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        result: List[List[int]] = []
        while working:
            current = working.pop()
            merged = False
            for idx, existing in enumerate(result):
                if _boxes_touch_or_overlap(tuple(current), tuple(existing)):
                    existing[0] = min(existing[0], current[0])
                    existing[1] = min(existing[1], current[1])
                    existing[2] = max(existing[2], current[2])
                    existing[3] = max(existing[3], current[3])
                    changed = True
                    merged = True
                    break
            if not merged:
                result.append(current)
        working = result
    return [tuple(map(int, b)) for b in working]


def _map_boxes_to_page(
    boxes: Sequence[Rect],
    page_size: Tuple[int, int],
    offset: Tuple[int, int],
) -> List[Rect]:
    mapped: List[Rect] = []
    offset_x, offset_y = offset
    page_w, page_h = page_size
    for x1, y1, x2, y2 in boxes:
        x1_local = max(0, x1 - offset_x)
        y1_local = max(0, y1 - offset_y)
        x2_local = min(page_w, x2 - offset_x)
        y2_local = min(page_h, y2 - offset_y)
        if x2_local <= x1_local or y2_local <= y1_local:
            continue
        mapped.append((int(x1_local), int(y1_local), int(x2_local), int(y2_local)))
    return mapped


def run_compare(
    old_path: str,
    new_path: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> bytes:
    def log(message: str) -> None:
        if progress_callback:
            progress_callback(message)

    log(f"Opening OLD PDF: {old_path}")
    old_doc = fitz.open(old_path)
    log(f"Opening NEW PDF: {new_path}")
    new_doc = fitz.open(new_path)
    try:
        if old_doc.page_count == 0:
            raise ValueError("OLD PDF has no pages")
        if new_doc.page_count == 0:
            raise ValueError("NEW PDF has no pages")
        log(f"OLD PDF pages: {old_doc.page_count}")
        log(f"NEW PDF pages: {new_doc.page_count}")

        log("Rendering page 1 of each PDF at 300 DPI")
        old_image, old_w, old_h = _ensure_grayscale_pixmap(old_doc.load_page(0))
        new_image, new_w, new_h = _ensure_grayscale_pixmap(new_doc.load_page(0))

        canvas_w = max(old_w, new_w)
        canvas_h = max(old_h, new_h)
        letterbox_applied = (canvas_w != old_w) or (canvas_h != old_h) or (canvas_w != new_w) or (canvas_h != new_h)
        if letterbox_applied:
            log(f"Letterboxing enabled: canvas {canvas_w}x{canvas_h}")
        old_canvas, old_offset = _center_on_canvas(old_image, (canvas_h, canvas_w))
        new_canvas, new_offset = _center_on_canvas(new_image, (canvas_h, canvas_w))

        log("Computing change mask")
        blur_old = cv2.GaussianBlur(old_canvas, (BLUR_KSIZE, BLUR_KSIZE), 0)
        blur_new = cv2.GaussianBlur(new_canvas, (BLUR_KSIZE, BLUR_KSIZE), 0)
        absdiff = cv2.absdiff(blur_old, blur_new)
        _, change_mask = cv2.threshold(absdiff, THRESH, 255, cv2.THRESH_BINARY)
        kernel = np.ones((MORPH_KERNEL, MORPH_KERNEL), dtype=np.uint8)
        change_mask = cv2.morphologyEx(change_mask, cv2.MORPH_CLOSE, kernel)
        change_mask = cv2.dilate(change_mask, kernel, iterations=DILATE_ITERS)
        change_mask = cv2.erode(change_mask, kernel, iterations=ERODE_ITERS)

        log("Building ink masks and refining change regions")
        _, old_ink = cv2.threshold(blur_old, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        _, new_ink = cv2.threshold(blur_new, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        change_mask = cv2.bitwise_and(change_mask, cv2.bitwise_or(old_ink, new_ink))

        old_regions = cv2.bitwise_and(change_mask, old_ink)
        new_regions = cv2.bitwise_and(change_mask, new_ink)

        log("Extracting candidate boxes for OLD page")
        old_raw_boxes = _find_candidate_boxes(old_regions, old_ink, absdiff, (canvas_h, canvas_w))
        log("Extracting candidate boxes for NEW page")
        new_raw_boxes = _find_candidate_boxes(new_regions, new_ink, absdiff, (canvas_h, canvas_w))

        log("Merging rectangles")
        old_merged_boxes = _merge_boxes(old_raw_boxes)
        new_merged_boxes = _merge_boxes(new_raw_boxes)

        log(f"OLD boxes: raw={len(old_raw_boxes)}, merged={len(old_merged_boxes)}")
        log(f"NEW boxes: raw={len(new_raw_boxes)}, merged={len(new_merged_boxes)}")

        old_page_boxes = _map_boxes_to_page(old_merged_boxes, (old_w, old_h), old_offset)
        new_page_boxes = _map_boxes_to_page(new_merged_boxes, (new_w, new_h), new_offset)

        if not old_page_boxes and not new_page_boxes:
            log("No diffs detected")

        log("Composing output PDF")
        output_doc = fitz.open()
        output_doc.insert_pdf(old_doc, from_page=0, to_page=0)
        output_doc.insert_pdf(new_doc, from_page=0, to_page=0)

        old_page = output_doc.load_page(0)
        new_page = output_doc.load_page(1)

        if old_page_boxes:
            shape_old = old_page.new_shape()
            for x1, y1, x2, y2 in old_page_boxes:
                rect = fitz.Rect(
                    x1 * PIXEL_TO_POINT,
                    y1 * PIXEL_TO_POINT,
                    x2 * PIXEL_TO_POINT,
                    y2 * PIXEL_TO_POINT,
                )
                shape_old.draw_rect(rect)
            shape_old.finish(
                color=RED,
                fill=None,
                width=STROKE_WIDTH_PT,
                stroke_opacity=STROKE_OPACITY,
            )
            shape_old.commit(overlay=True)

        if new_page_boxes:
            shape_new = new_page.new_shape()
            for x1, y1, x2, y2 in new_page_boxes:
                rect = fitz.Rect(
                    x1 * PIXEL_TO_POINT,
                    y1 * PIXEL_TO_POINT,
                    x2 * PIXEL_TO_POINT,
                    y2 * PIXEL_TO_POINT,
                )
                shape_new.draw_rect(rect)
            shape_new.finish(
                color=GREEN,
                fill=None,
                width=STROKE_WIDTH_PT,
                stroke_opacity=STROKE_OPACITY,
            )
            shape_new.commit(overlay=True)

        pdf_bytes = output_doc.tobytes()
        output_doc.close()
        return pdf_bytes
    finally:
        old_doc.close()
        new_doc.close()


class CompareWorker(QObject):
    progress = Signal(str)
    done = Signal(bytes)
    error = Signal(str)

    def __init__(self, old_path: str, new_path: str) -> None:
        super().__init__()
        self.old_path = old_path
        self.new_path = new_path

    @Slot()
    def run(self) -> None:
        try:
            result = run_compare(self.old_path, self.new_path, self.progress.emit)
            self.done.emit(result)
        except Exception as exc:  # pragma: no cover - safety net
            tb_last_line = traceback.format_exc().splitlines()[-1]
            message = f"{exc.__class__.__name__}: {exc} [{tb_last_line}]"
            self.error.emit(message)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Compare SET – Desktop")
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[CompareWorker] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget(self)
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        central.setLayout(layout)

        self.old_edit = QLineEdit()
        self.old_edit.setReadOnly(True)
        self.new_edit = QLineEdit()
        self.new_edit.setReadOnly(True)

        old_label = QLabel("Old revision (PDF)")
        new_label = QLabel("New revision (PDF)")

        self.old_browse = QPushButton("Browse…")
        self.old_browse.clicked.connect(lambda: self._choose_file(self.old_edit))
        self.new_browse = QPushButton("Browse…")
        self.new_browse.clicked.connect(lambda: self._choose_file(self.new_edit))

        self.compare_button = QPushButton("Compare")
        self.compare_button.clicked.connect(self._start_compare)
        self.compare_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        helper = QLabel("Engine is fixed in code. Output: 2-page PDF with translucent rectangles.")
        helper.setStyleSheet("color: #666666; font-size: 11px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold;")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(160)
        self.log_box.setLineWrapMode(QTextEdit.NoWrap)
        self.log_box.setFontFamily("Consolas")

        layout.addWidget(old_label, 0, 0)
        layout.addWidget(self.old_edit, 0, 1)
        layout.addWidget(self.old_browse, 0, 2)

        layout.addWidget(new_label, 1, 0)
        layout.addWidget(self.new_edit, 1, 1)
        layout.addWidget(self.new_browse, 1, 2)

        layout.addWidget(self.compare_button, 2, 0, 1, 3)
        layout.addWidget(helper, 3, 0, 1, 3)
        layout.addWidget(self.progress_bar, 4, 0, 1, 3)
        layout.addWidget(self.status_label, 5, 0, 1, 3)
        layout.addWidget(self.log_box, 6, 0, 1, 3)

        self.setCentralWidget(central)
        self.resize(720, 480)

    def _choose_file(self, target_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF",
            os.path.dirname(target_edit.text()) if target_edit.text() else "",
            "PDF Files (*.pdf)",
        )
        if path:
            target_edit.setText(path)

    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")
        self.log_box.moveCursor(QTextCursor.End)

    def _validate_path(self, path: str, label: str) -> Optional[str]:
        if not path:
            return f"{label} is required."
        if not path.lower().endswith(".pdf"):
            return f"{label} must be a PDF file."
        if not os.path.isfile(path):
            return f"{label} not found."
        return None

    def _start_compare(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            return
        old_path = self.old_edit.text().strip()
        new_path = self.new_edit.text().strip()
        for label, path in (("Old revision", old_path), ("New revision", new_path)):
            error = self._validate_path(path, label)
            if error:
                QMessageBox.warning(self, "Invalid Input", error)
                return

        self.compare_button.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Running comparison…")
        self.append_log("Starting comparison run")

        self.worker_thread = QThread(self)
        self.worker = CompareWorker(old_path, new_path)
        self.worker.moveToThread(self.worker_thread)
        self.worker.progress.connect(self.append_log)
        self.worker.done.connect(self._handle_done)
        self.worker.error.connect(self._handle_error)
        self.worker.done.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)
        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

    @Slot()
    def _cleanup_worker(self) -> None:
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.worker_thread:
            self.worker_thread.deleteLater()
            self.worker_thread = None
        self.compare_button.setEnabled(True)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

    @Slot(bytes)
    def _handle_done(self, pdf_bytes: bytes) -> None:
        self.status_label.setText("Compare finished")
        self.append_log("Comparison complete. Awaiting save location")
        suggested_name = f"CompareSet_Result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        default_dir = os.path.dirname(self.new_edit.text()) or os.getcwd()
        default_path = os.path.join(default_dir, suggested_name)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Comparison Result",
            default_path,
            "PDF Files (*.pdf)",
        )
        if not save_path:
            self.append_log("Save cancelled by user")
            self.status_label.setText("Ready")
            return
        if not save_path.lower().endswith(".pdf"):
            save_path += ".pdf"
        try:
            with open(save_path, "wb") as fh:
                fh.write(pdf_bytes)
        except OSError as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to write file: {exc}")
            self.append_log(f"Save error: {exc}")
            self.status_label.setText("Error during save")
            return
        self.append_log(f"Saved result to: {save_path}")
        self.status_label.setText("Ready")
        QMessageBox.information(self, "Compare SET", "Comparison PDF saved successfully.")

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        self.status_label.setText("Error")
        self.append_log(message)
        QMessageBox.critical(self, "Comparison Failed", message)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
