import type { PixelRegion } from "./types";

export interface Transform {
  scale: number;
  canvasHeightPx: number;
}

/**
 * Converts a pixel-based bounding box into PDF user units using the provided transform.
 */
export function pixelBBoxToPdf(
  region: PixelRegion,
  transform: Transform,
): [number, number, number, number] {
  const { scale, canvasHeightPx } = transform;
  const x0 = round2(region.minX / scale);
  const x1 = round2(region.maxX / scale);
  const y0 = round2((canvasHeightPx - region.maxY) / scale);
  const y1 = round2((canvasHeightPx - region.minY) / scale);
  return [x0, y0, x1, y1];
}

export function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

export function mmToPt(mm: number): number {
  return (mm / 25.4) * 72;
}
