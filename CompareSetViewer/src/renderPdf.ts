import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import type { PDFDocumentProxy } from "pdfjs-dist/types/src/display/api";
import type { PixelBuffer } from "./types";

GlobalWorkerOptions.workerSrc = "";

export interface LoadedPdf {
  doc: PDFDocumentProxy;
  pageCount: number;
}

export async function loadPdf(base64: string): Promise<LoadedPdf | null> {
  if (!base64) {
    return null;
  }
  const bytes = base64ToUint8Array(base64);
  const loadingTask = getDocument({ data: bytes, useWorkerFetch: false, isEvalSupported: false });
  const doc = await loadingTask.promise;
  return { doc, pageCount: doc.numPages };
}

export async function renderPage(
  doc: PDFDocumentProxy | null,
  pageIndex: number,
  scale: number,
  targetWidth: number,
  targetHeight: number,
): Promise<{ pixels: PixelBuffer; widthPt: number; heightPt: number }> {
  if (!doc) {
    return {
      pixels: blankBuffer(targetWidth, targetHeight),
      widthPt: targetWidth / scale,
      heightPt: targetHeight / scale,
    };
  }
  const pageNumber = pageIndex + 1;
  if (pageNumber > doc.numPages) {
    return {
      pixels: blankBuffer(targetWidth, targetHeight),
      widthPt: targetWidth / scale,
      heightPt: targetHeight / scale,
    };
  }

  const page = await doc.getPage(pageNumber);
  const viewport = page.getViewport({ scale });
  const renderCanvas = createCanvas(viewport.width, viewport.height);
  const ctx = renderCanvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) {
    throw new Error("Unable to obtain canvas context for rendering.");
  }
  ctx.fillStyle = "white";
  ctx.fillRect(0, 0, viewport.width, viewport.height);

  await page.render({ canvasContext: ctx, viewport }).promise;
  const image = ctx.getImageData(0, 0, viewport.width, viewport.height).data;
  const grayscale = new Uint8ClampedArray(targetWidth * targetHeight);
  grayscale.fill(255);

  const xOffset = 0;
  const yOffset = targetHeight - viewport.height;

  for (let y = 0; y < viewport.height; y += 1) {
    const targetY = y + yOffset;
    if (targetY < 0 || targetY >= targetHeight) {
      continue;
    }
    for (let x = 0; x < viewport.width; x += 1) {
      const targetX = x + xOffset;
      if (targetX < 0 || targetX >= targetWidth) {
        continue;
      }
      const srcIndex = (y * viewport.width + x) * 4;
      const r = image[srcIndex];
      const g = image[srcIndex + 1];
      const b = image[srcIndex + 2];
      const gray = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
      grayscale[targetY * targetWidth + targetX] = gray;
    }
  }

  return {
    pixels: { width: targetWidth, height: targetHeight, data: grayscale },
    widthPt: viewport.width / scale,
    heightPt: viewport.height / scale,
  };
}

export function destroyPdf(doc: LoadedPdf | null): void {
  if (doc) {
    doc.doc.destroy();
  }
}

function blankBuffer(width: number, height: number): PixelBuffer {
  return {
    width,
    height,
    data: new Uint8ClampedArray(width * height).fill(255),
  };
}

function createCanvas(width: number, height: number): HTMLCanvasElement | OffscreenCanvas {
  if (typeof OffscreenCanvas !== "undefined") {
    return new OffscreenCanvas(width, height);
  }
  if (typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }
  throw new Error("Canvas not supported in this environment.");
}

function base64ToUint8Array(base64: string): Uint8Array {
  const normalized = base64.includes(",") ? base64.split(",").pop() ?? base64 : base64;
  let binary = "";
  if (typeof atob === "function") {
    binary = atob(normalized);
  } else if (typeof Buffer !== "undefined") {
    binary = Buffer.from(normalized, "base64").toString("binary");
  } else {
    throw new Error("Base64 decoding not supported in this environment.");
  }
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}
