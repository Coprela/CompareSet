import { mmToPt, pixelBBoxToPdf } from "./coords";
import type { DiffKind, DiffRegion, PixelRegion } from "./types";

export interface RegionContext {
  pageIndex: number;
  gridRows: number;
  gridCols: number;
  pageWidthPt: number;
  pageHeightPt: number;
  scale: number;
  canvasHeightPx: number;
}

const MIN_DIM_PT = mmToPt(0.2);

export function classifyRegions(
  regions: PixelRegion[],
  ctx: RegionContext,
): DiffRegion[] {
  const result: DiffRegion[] = [];
  for (const region of regions) {
    const bboxPdf = pixelBBoxToPdf(region, { scale: ctx.scale, canvasHeightPx: ctx.canvasHeightPx });
    const widthPt = bboxPdf[2] - bboxPdf[0];
    const heightPt = bboxPdf[3] - bboxPdf[1];
    if (widthPt < MIN_DIM_PT || heightPt < MIN_DIM_PT) {
      continue;
    }

    const meanOld = region.sumOld / region.area;
    const meanNew = region.sumNew / region.area;
    const type = resolveType(meanOld, meanNew);
    const gridCell = gridLabel(bboxPdf, ctx.pageWidthPt, ctx.pageHeightPt, ctx.gridCols, ctx.gridRows);

    result.push({
      pageIndex: ctx.pageIndex,
      gridCell,
      bboxPdfUnits: bboxPdf,
      type,
      areaPx: region.area,
    });
  }
  return result;
}

function resolveType(meanOld: number, meanNew: number): DiffKind {
  const activeOld = meanOld < 245;
  const activeNew = meanNew < 245;
  if (activeOld && !activeNew) {
    return "removed";
  }
  if (!activeOld && activeNew) {
    return "added";
  }
  return "modified";
}

function gridLabel(
  bbox: [number, number, number, number],
  widthPt: number,
  heightPt: number,
  cols: number,
  rows: number,
): string {
  const centerX = (bbox[0] + bbox[2]) / 2;
  const centerY = (bbox[1] + bbox[3]) / 2;
  const cellWidth = widthPt / cols;
  const cellHeight = heightPt / rows;
  const colIndex = clamp(Math.floor(centerX / cellWidth), 0, cols - 1) + 1;
  const rowIndex = clamp(Math.floor(centerY / cellHeight), 0, rows - 1) + 1;
  return `${rowIndex}x${colIndex}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
