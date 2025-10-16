/**
 * Shared type declarations for the CompareSet PCF engine.
 */

export interface CompareConfig {
  oldPdfBase64: string;
  newPdfBase64: string;
  dpi: number;
  gridRows: number;
  gridCols: number;
  diffThreshold: number;
  minRegionArea: number;
  strokeWidthPt: number;
  overlayAlpha: number;
  colorRemoved: string;
  colorAdded: string;
}

export interface PixelBuffer {
  width: number;
  height: number;
  /**
   * Grayscale pixel intensities [0,255].
   */
  data: Uint8ClampedArray;
}

export type DiffKind = "removed" | "added" | "modified";

export interface DiffRegion {
  pageIndex: number;
  gridCell: string;
  bboxPdfUnits: [number, number, number, number];
  type: DiffKind;
  areaPx: number;
}

export interface PixelRegion {
  area: number;
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  sumOld: number;
  sumNew: number;
}

export interface PageCompareContext {
  pageIndex: number;
  canvasWidthPx: number;
  canvasHeightPx: number;
  pageWidthPt: number;
  pageHeightPt: number;
  scale: number;
  oldPixels: PixelBuffer;
  newPixels: PixelBuffer;
}

export interface PageCompareResult extends PageCompareContext {
  regions: DiffRegion[];
}

export interface CompareArtifacts {
  pages: PageCompareResult[];
  outputPdfBase64: string | null;
}

export interface CompareResult {
  outputPdfBase64: string | null;
  diffSummaryJson: string | null;
  diffCount: number;
  status: string;
}

export interface ProgressMessage {
  type: "progress";
  text: string;
}

export type WorkerRequest =
  | { type: "compare"; payload: CompareConfig };

export type WorkerResponse = CompareResult | ProgressMessage;
