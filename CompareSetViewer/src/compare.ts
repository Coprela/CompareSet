import { computeDiff } from "./diff";
import { classifyRegions } from "./regions";
import { buildOverlayPdf } from "./overlayPdf";
import { loadPdf, renderPage, destroyPdf } from "./renderPdf";
import type {
  CompareConfig,
  CompareResult,
  PageCompareResult,
  ProgressMessage,
} from "./types";

export async function comparePdfs(
  config: CompareConfig,
  progress: (message: ProgressMessage) => void,
): Promise<CompareResult> {
  let oldDoc: Awaited<ReturnType<typeof loadPdf>> | null = null;
  let newDoc: Awaited<ReturnType<typeof loadPdf>> | null = null;
  try {
    progress({ type: "progress", text: "Loading PDFs..." });
    [oldDoc, newDoc] = await Promise.all([loadPdf(config.oldPdfBase64), loadPdf(config.newPdfBase64)]);

    const pageCount = Math.max(oldDoc?.pageCount ?? 0, newDoc?.pageCount ?? 0);
    const scale = config.dpi / 72;
    const pages: PageCompareResult[] = [];

    for (let index = 0; index < pageCount; index += 1) {
      progress({ type: "progress", text: `Rendering page ${index + 1}/${pageCount}...` });
      const oldDimensions = await renderPageDimension(oldDoc?.doc, index, scale);
      const newDimensions = await renderPageDimension(newDoc?.doc, index, scale);
      const canvasWidth = Math.max(1, Math.max(oldDimensions.widthPx, newDimensions.widthPx));
      const canvasHeight = Math.max(1, Math.max(oldDimensions.heightPx, newDimensions.heightPx));

      const { pixels: oldPixels, widthPt: oldWidthPt, heightPt: oldHeightPt } = await renderPage(
        oldDoc?.doc ?? null,
        index,
        scale,
        canvasWidth,
        canvasHeight,
      );
      const { pixels: newPixels, widthPt: newWidthPt, heightPt: newHeightPt } = await renderPage(
        newDoc?.doc ?? null,
        index,
        scale,
        canvasWidth,
        canvasHeight,
      );

      const pageWidthPt = Math.max(oldWidthPt, newWidthPt);
      const pageHeightPt = Math.max(oldHeightPt, newHeightPt);

      progress({ type: "progress", text: `Diffing page ${index + 1}/${pageCount}...` });
      const diff = computeDiff(oldPixels, newPixels, config.diffThreshold, config.minRegionArea);
      const regions = classifyRegions(diff.regions, {
        pageIndex: index,
        gridRows: config.gridRows,
        gridCols: config.gridCols,
        pageWidthPt,
        pageHeightPt,
        scale,
        canvasHeightPx: canvasHeight,
      });

      pages.push({
        pageIndex: index,
        canvasWidthPx: canvasWidth,
        canvasHeightPx: canvasHeight,
        pageWidthPt,
        pageHeightPt,
        scale,
        oldPixels,
        newPixels,
        regions,
      });
    }

    progress({ type: "progress", text: "Building overlay PDF..." });
    const outputPdfBase64 = await buildOverlayPdf({
      config,
      pages,
      oldPdfBase64: config.oldPdfBase64,
      newPdfBase64: config.newPdfBase64,
    });

    const diffSummaryJson = JSON.stringify(pages.flatMap((p) => p.regions));

    return {
      outputPdfBase64,
      diffSummaryJson,
      diffCount: pages.reduce((acc, p) => acc + p.regions.length, 0),
      status: "Completed",
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      outputPdfBase64: null,
      diffSummaryJson: null,
      diffCount: 0,
      status: `Error: ${message}`,
    };
  } finally {
    destroyPdf(oldDoc);
    destroyPdf(newDoc);
  }
}

async function renderPageDimension(
  doc: import("pdfjs-dist/types/src/display/api").PDFDocumentProxy | undefined,
  index: number,
  scale: number,
): Promise<{ widthPx: number; heightPx: number }> {
  if (!doc || index + 1 > doc.numPages) {
    return { widthPx: 0, heightPx: 0 };
  }
  const page = await doc.getPage(index + 1);
  const viewport = page.getViewport({ scale });
  return { widthPx: Math.ceil(viewport.width), heightPx: Math.ceil(viewport.height) };
}
