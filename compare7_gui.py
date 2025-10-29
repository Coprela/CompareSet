#!/usr/bin/env python3
"""compare7_gui

REQUIREMENTS:
PySide6
pymupdf
opencv-python
numpy
"""
from __future__ import annotations

import datetime
import os
import sys
import traceback
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import cv2
import fitz
import numpy as np
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

DPI = 300
BLUR_KSIZE = 3
THRESH = 25
MORPH_KERNEL = 3
DILATE_ITERS = 2
ERODE_ITERS = 1
MIN_AREA = 36
STROKE_WIDTH_PT = 0.8
STROKE_OPACITY = 0.6
RED = (1.0, 0.0, 0.0)
GREEN = (0.0, 1.0, 0.0)


def _ensure_pdf(path: str) -> None:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    if not path.lower().endswith(".pdf"):
        raise ValueError(f"Not a PDF file: {path}")


def _merge_boxes(boxes: Sequence[Tuple[int, int, int, int]]) -> List[Tuple[int, int, int, int]]:
    def overlaps(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
        return not (
            a[2] < b[0] - 1
            or a[0] > b[2] + 1
            or a[3] < b[1] - 1
            or a[1] > b[3] + 1
        )

    pending: List[Tuple[int, int, int, int]] = list(boxes)
    merged: List[Tuple[int, int, int, int]] = []

    while pending:
        current = pending.pop()
        merged_with_existing = False
        for idx, other in enumerate(merged):
            if overlaps(current, other):
                combined = (
                    min(current[0], other[0]),
                    min(current[1], other[1]),
                    max(current[2], other[2]),
                    max(current[3], other[3]),
                )
                if combined != other:
                    merged[idx] = combined
                    pending.append(combined)
                merged_with_existing = True
                break
        if not merged_with_existing:
            merged.append(current)

    return merged


def _clip_box(
    box: Tuple[int, int, int, int],
    width: int,
    height: int,
) -> Optional[Tuple[int, int, int, int]]:
    x1, y1, x2, y2 = box
    x1 = max(0, min(width, x1))
    y1 = max(0, min(height, y1))
    x2 = max(0, min(width, x2))
    y2 = max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def run_compare(
    old_path: str,
    new_path: str,
    logger: Optional[Callable[[str], None]] = None,
) -> bytes:
    log = logger or (lambda message: None)
    _ensure_pdf(old_path)
    _ensure_pdf(new_path)

    log(f"Opening OLD PDF: {old_path}")
    old_doc = fitz.open(old_path)
    if old_doc.page_count == 0:
        raise ValueError("Old PDF has no pages")
    log(f"OLD page count: {old_doc.page_count}")

    log(f"Opening NEW PDF: {new_path}")
    new_doc = fitz.open(new_path)
    if new_doc.page_count == 0:
        raise ValueError("New PDF has no pages")
    log(f"NEW page count: {new_doc.page_count}")

    old_page = old_doc[0]
    new_page = new_doc[0]

    zoom = DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    old_pix = old_page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)
    new_pix = new_page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)

    old_img = np.frombuffer(old_pix.samples, dtype=np.uint8).reshape(old_pix.height, old_pix.width)
    new_img = np.frombuffer(new_pix.samples, dtype=np.uint8).reshape(new_pix.height, new_pix.width)

    log(
        "Rendered sizes: "
        f"old={old_img.shape[1]}x{old_img.shape[0]}, "
        f"new={new_img.shape[1]}x{new_img.shape[0]}"
    )

    canvas_height = max(old_img.shape[0], new_img.shape[0])
    canvas_width = max(old_img.shape[1], new_img.shape[1])

    old_offset = (0, 0)
    new_offset = (0, 0)

    if old_img.shape != new_img.shape:
        log(
            "Letterboxing applied to align render sizes"
        )
        old_canvas = np.zeros((canvas_height, canvas_width), dtype=np.uint8)
        new_canvas = np.zeros((canvas_height, canvas_width), dtype=np.uint8)

        old_offset = ((canvas_width - old_img.shape[1]) // 2, (canvas_height - old_img.shape[0]) // 2)
        new_offset = ((canvas_width - new_img.shape[1]) // 2, (canvas_height - new_img.shape[0]) // 2)
        log(f"Old offset: {old_offset}, New offset: {new_offset}")

        old_canvas[
            old_offset[1] : old_offset[1] + old_img.shape[0],
            old_offset[0] : old_offset[0] + old_img.shape[1],
        ] = old_img
        new_canvas[
            new_offset[1] : new_offset[1] + new_img.shape[0],
            new_offset[0] : new_offset[0] + new_img.shape[1],
        ] = new_img
    else:
        old_canvas = old_img
        new_canvas = new_img

    blurred_old = cv2.GaussianBlur(old_canvas, (BLUR_KSIZE, BLUR_KSIZE), 0)
    blurred_new = cv2.GaussianBlur(new_canvas, (BLUR_KSIZE, BLUR_KSIZE), 0)

    diff = cv2.absdiff(blurred_old, blurred_new)
    _, thresh = cv2.threshold(diff, THRESH, 255, cv2.THRESH_BINARY)

    kernel = np.ones((MORPH_KERNEL, MORPH_KERNEL), np.uint8)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    dilated = cv2.dilate(closed, kernel, iterations=DILATE_ITERS)
    processed = cv2.erode(dilated, kernel, iterations=ERODE_ITERS)

    contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes: List[Tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w * h >= MIN_AREA:
            boxes.append((x, y, x + w, y + h))

    log(f"Raw diff boxes: {len(boxes)}")
    merged_boxes = _merge_boxes(boxes)
    log(f"Merged diff boxes: {len(merged_boxes)}")

    if not merged_boxes:
        log("No diffs detected")

    def map_boxes(
        boxes_in: Iterable[Tuple[int, int, int, int]],
        offset: Tuple[int, int],
        width: int,
        height: int,
    ) -> List[fitz.Rect]:
        mapped: List[fitz.Rect] = []
        scale = 72.0 / DPI
        for box in boxes_in:
            local_box = (
                box[0] - offset[0],
                box[1] - offset[1],
                box[2] - offset[0],
                box[3] - offset[1],
            )
            clipped = _clip_box(local_box, width, height)
            if not clipped:
                continue
            lx1, ly1, lx2, ly2 = clipped
            rect = fitz.Rect(
                lx1 * scale,
                ly1 * scale,
                lx2 * scale,
                ly2 * scale,
            )
            mapped.append(rect)
        return mapped

    old_rects = map_boxes(merged_boxes, old_offset, old_img.shape[1], old_img.shape[0])
    new_rects = map_boxes(merged_boxes, new_offset, new_img.shape[1], new_img.shape[0])

    log("Composing output PDF")
    output_doc = fitz.open()
    output_doc.insert_pdf(old_doc, from_page=0, to_page=0)
    output_doc.insert_pdf(new_doc, from_page=0, to_page=0)

    page_old = output_doc[0]
    if old_rects:
        shape_old = page_old.new_shape()
        for rect in old_rects:
            shape_old.draw_rect(rect)
        shape_old.finish(
            color=RED,
            fill=None,
            width=STROKE_WIDTH_PT,
            stroke_opacity=STROKE_OPACITY,
        )
        shape_old.commit(overlay=True)

    page_new = output_doc[1]
    if new_rects:
        shape_new = page_new.new_shape()
        for rect in new_rects:
            shape_new.draw_rect(rect)
        shape_new.finish(
            color=GREEN,
            fill=None,
            width=STROKE_WIDTH_PT,
            stroke_opacity=STROKE_OPACITY,
        )
        shape_new.commit(overlay=True)

    pdf_bytes = output_doc.tobytes()
    log("Output PDF bytes ready")

    output_doc.close()
    old_doc.close()
    new_doc.close()

    return pdf_bytes


class CompareWorker(QObject):
    progress = Signal(str)
    done = Signal(bytes)
    error = Signal(str)

    def __init__(self, old_path: str, new_path: str) -> None:
        super().__init__()
        self._old_path = old_path
        self._new_path = new_path

    @Slot()
    def run(self) -> None:
        try:
            result = run_compare(self._old_path, self._new_path, logger=self.progress.emit)
            self.done.emit(result)
        except Exception as exc:  # pylint: disable=broad-except
            tb_line = traceback.format_exc().strip().splitlines()[-1]
            self.progress.emit(f"Traceback: {tb_line}")
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Compare 7 – Desktop")
        self.resize(680, 420)

        self._thread: Optional[QThread] = None
        self._worker: Optional[CompareWorker] = None

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        # Row for old PDF
        row_old = QHBoxLayout()
        label_old = QLabel("Old revision (PDF)")
        self.old_path_edit = QLineEdit()
        self.old_path_edit.setReadOnly(True)
        browse_old = QPushButton("Browse…")
        browse_old.clicked.connect(self._browse_old)
        row_old.addWidget(label_old)
        row_old.addWidget(self.old_path_edit, 1)
        row_old.addWidget(browse_old)

        # Row for new PDF
        row_new = QHBoxLayout()
        label_new = QLabel("New revision (PDF)")
        self.new_path_edit = QLineEdit()
        self.new_path_edit.setReadOnly(True)
        browse_new = QPushButton("Browse…")
        browse_new.clicked.connect(self._browse_new)
        row_new.addWidget(label_new)
        row_new.addWidget(self.new_path_edit, 1)
        row_new.addWidget(browse_new)

        self.compare_button = QPushButton("Compare")
        self.compare_button.setDefault(True)
        self.compare_button.setFixedHeight(40)
        self.compare_button.clicked.connect(self._start_comparison)

        info_label = QLabel(
            "Engine is fixed in code. Output: 2-page PDF with translucent rectangles."
        )
        info_label.setStyleSheet("color: #666666; font-size: 11px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #333333;")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setMinimumHeight(100)
        self.log_text.setMaximumHeight(160)
        self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        card_layout.addLayout(row_old)
        card_layout.addLayout(row_new)
        card_layout.addWidget(self.compare_button)
        card_layout.addWidget(info_label)
        card_layout.addWidget(self.progress_bar)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.log_text)

        main_layout.addWidget(card)
        self.setCentralWidget(central)

        self._append_log("Ready")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        event.accept()

    def _append_log(self, message: str) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.ensureCursorVisible()

    def _browse_old(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Old PDF",
            self._suggest_start_directory(self.old_path_edit.text()),
            "PDF Files (*.pdf)",
        )
        if path:
            self.old_path_edit.setText(path)
            self._append_log(f"Selected OLD PDF: {path}")

    def _browse_new(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select New PDF",
            self._suggest_start_directory(self.new_path_edit.text()),
            "PDF Files (*.pdf)",
        )
        if path:
            self.new_path_edit.setText(path)
            self._append_log(f"Selected NEW PDF: {path}")

    def _suggest_start_directory(self, current_path: str) -> str:
        if current_path and os.path.isdir(os.path.dirname(current_path)):
            return os.path.dirname(current_path)
        return os.path.expanduser("~")

    def _validate_inputs(self, old_path: str, new_path: str) -> Optional[str]:
        if not old_path:
            return "Please choose the old PDF."
        if not new_path:
            return "Please choose the new PDF."
        if not os.path.isfile(old_path):
            return "Old PDF does not exist."
        if not os.path.isfile(new_path):
            return "New PDF does not exist."
        if not old_path.lower().endswith(".pdf"):
            return "Old file must be a PDF."
        if not new_path.lower().endswith(".pdf"):
            return "New file must be a PDF."
        return None

    def _start_comparison(self) -> None:
        if self._thread is not None:
            return

        old_path = self.old_path_edit.text().strip()
        new_path = self.new_path_edit.text().strip()
        error = self._validate_inputs(old_path, new_path)
        if error:
            QMessageBox.warning(self, "Compare 7", error)
            self._append_log(f"Validation failed: {error}")
            return

        self.compare_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Processing…")
        self.status_label.setStyleSheet("color: #333333;")
        self._append_log("Starting comparison job")

        thread = QThread()
        worker = CompareWorker(old_path, new_path)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._append_log)
        worker.done.connect(self._handle_done)
        worker.error.connect(self._handle_error)
        worker.done.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _handle_done(self, result: bytes) -> None:
        self._append_log("Comparison finished – prompting for save location")
        old_path = self.old_path_edit.text().strip()
        default_dir = os.path.dirname(old_path) if old_path else os.path.expanduser("~")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"CompareSet_Result_{timestamp}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save comparison result",
            os.path.join(default_dir, default_name),
            "PDF Files (*.pdf)",
        )
        if file_path:
            try:
                with open(file_path, "wb") as fh:
                    fh.write(result)
                self._append_log(f"Result saved: {file_path}")
                self.status_label.setText(f"Done: {file_path}")
                self.status_label.setStyleSheet("color: #0a6b0d;")
            except Exception as exc:  # pylint: disable=broad-except
                QMessageBox.critical(self, "Compare 7", f"Could not save file: {exc}")
                self._append_log(f"Save error: {exc}")
                self.status_label.setText("Error saving file")
                self.status_label.setStyleSheet("color: #b00020;")
        else:
            self._append_log("Save dialog canceled by user")
            self.status_label.setText("Canceled")
            self.status_label.setStyleSheet("color: #333333;")
        self._cleanup_after_task()

    def _handle_error(self, message: str) -> None:
        self._append_log(f"Worker error: {message}")
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: #b00020;")
        QMessageBox.critical(self, "Compare 7", message)
        self._cleanup_after_task()

    def _cleanup_after_task(self) -> None:
        self.progress_bar.setVisible(False)
        self.compare_button.setEnabled(True)
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

# Suggested packaging command:
# pyinstaller --noconfirm --windowed --onefile compare7_gui.py
