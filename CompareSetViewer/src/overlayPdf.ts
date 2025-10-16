import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import type { CompareConfig, DiffRegion, PageCompareResult } from "./types";

interface OverlayOptions {
  config: CompareConfig;
  pages: PageCompareResult[];
  oldPdfBase64: string;
  newPdfBase64: string;
}

export async function buildOverlayPdf(options: OverlayOptions): Promise<string> {
  const { config, pages, oldPdfBase64, newPdfBase64 } = options;
  const oldDoc = oldPdfBase64 ? await PDFDocument.load(normalizeBase64(oldPdfBase64)) : await PDFDocument.create();
  const newDoc = newPdfBase64 ? await PDFDocument.load(normalizeBase64(newPdfBase64)) : await PDFDocument.create();
  const result = await PDFDocument.create();
  const labelFont = await result.embedFont(StandardFonts.Helvetica);

  if (pages.length === 0) {
    result.addPage([612, 792]);
  }

  for (const page of pages) {
    const oldPage = await importPage(result, oldDoc, page.pageIndex, page.pageWidthPt, page.pageHeightPt);
    const newPage = await importPage(result, newDoc, page.pageIndex, page.pageWidthPt, page.pageHeightPt);

    const removedColor = hexToRgb(config.colorRemoved);
    const addedColor = hexToRgb(config.colorAdded);

    for (const region of page.regions) {
      if (region.type === "added") {
        continue;
      }
      drawRegion(oldPage, region, config, removedColor, labelFont);
    }

    for (const region of page.regions) {
      if (region.type === "removed") {
        continue;
      }
      drawRegion(newPage, region, config, addedColor, labelFont);
    }
  }

  const bytes = await result.save();
  return uint8ToBase64(bytes);
}

async function importPage(
  target: PDFDocument,
  source: PDFDocument,
  index: number,
  fallbackWidth: number,
  fallbackHeight: number,
) {
  if (index < source.getPageCount()) {
    const [copied] = await target.copyPages(source, [index]);
    target.addPage(copied);
    return copied;
  }
  const page = target.addPage([fallbackWidth, fallbackHeight]);
  return page;
}

function drawRegion(
  page: import("pdf-lib").PDFPage,
  region: DiffRegion,
  config: CompareConfig,
  color: { r: number; g: number; b: number },
  font: import("pdf-lib").PDFFont,
): void {
  const [x0, y0, x1, y1] = region.bboxPdfUnits;
  const width = x1 - x0;
  const height = y1 - y0;
  page.drawRectangle({
    x: x0,
    y: y0,
    width,
    height,
    borderWidth: config.strokeWidthPt,
    borderColor: rgb(color.r, color.g, color.b),
    color: rgb(color.r, color.g, color.b),
    opacity: config.overlayAlpha,
  });

  const label = region.gridCell;
  const fontSize = Math.max(6, Math.min(12, height / 4));
  const textColor = rgb(color.r, color.g, color.b);
  page.drawText(label, {
    x: x0 + config.strokeWidthPt,
    y: y1 - fontSize - config.strokeWidthPt,
    size: fontSize,
    font,
    color: textColor,
  });
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const normalized = hex.replace("#", "");
  const bigint = parseInt(normalized, 16);
  const r = ((bigint >> 16) & 255) / 255;
  const g = ((bigint >> 8) & 255) / 255;
  const b = (bigint & 255) / 255;
  return { r, g, b };
}

function normalizeBase64(base64: string): Uint8Array {
  const normalized = base64.includes(",") ? base64.split(",").pop() ?? base64 : base64;
  if (typeof atob !== "function") {
    throw new Error("atob not available for base64 decoding");
  }
  const binary = atob(normalized);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function uint8ToBase64(bytes: Uint8Array): string {
  if (typeof btoa !== "function") {
    throw new Error("btoa not available for base64 encoding");
  }
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
