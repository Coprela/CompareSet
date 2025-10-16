import type { PixelBuffer, PixelRegion } from "./types";

export interface DiffComputation {
  regions: PixelRegion[];
  mask: Uint8Array;
}

export function computeDiff(
  oldPixels: PixelBuffer,
  newPixels: PixelBuffer,
  threshold: number,
  minArea: number,
): DiffComputation {
  const { width, height } = oldPixels;
  if (width !== newPixels.width || height !== newPixels.height) {
    throw new Error("Pixel buffers must have matching dimensions.");
  }

  const mask = new Uint8Array(width * height);
  for (let i = 0; i < mask.length; i += 1) {
    const diff = Math.abs(oldPixels.data[i] - newPixels.data[i]);
    mask[i] = diff > threshold ? 1 : 0;
  }

  const closed = morphClose(mask, width, height);
  const opened = morphOpen(closed, width, height);
  const regions = findRegions(opened, width, height, oldPixels, newPixels, minArea);

  return { regions, mask: opened };
}

function morphClose(mask: Uint8Array, width: number, height: number): Uint8Array {
  return erode(dilate(mask, width, height), width, height);
}

function morphOpen(mask: Uint8Array, width: number, height: number): Uint8Array {
  return dilate(erode(mask, width, height), width, height);
}

function dilate(mask: Uint8Array, width: number, height: number): Uint8Array {
  const result = new Uint8Array(mask.length);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let on = 0;
      for (let dy = -1; dy <= 1 && !on; dy += 1) {
        const ny = y + dy;
        if (ny < 0 || ny >= height) {
          continue;
        }
        for (let dx = -1; dx <= 1; dx += 1) {
          const nx = x + dx;
          if (nx < 0 || nx >= width) {
            continue;
          }
          if (mask[ny * width + nx] > 0) {
            on = 1;
            break;
          }
        }
      }
      result[y * width + x] = on;
    }
  }
  return result;
}

function erode(mask: Uint8Array, width: number, height: number): Uint8Array {
  const result = new Uint8Array(mask.length);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let on = 1;
      for (let dy = -1; dy <= 1 && on; dy += 1) {
        const ny = y + dy;
        if (ny < 0 || ny >= height) {
          on = 0;
          break;
        }
        for (let dx = -1; dx <= 1; dx += 1) {
          const nx = x + dx;
          if (nx < 0 || nx >= width) {
            on = 0;
            break;
          }
          if (!mask[ny * width + nx]) {
            on = 0;
            break;
          }
        }
      }
      result[y * width + x] = on;
    }
  }
  return result;
}

function findRegions(
  mask: Uint8Array,
  width: number,
  height: number,
  oldPixels: PixelBuffer,
  newPixels: PixelBuffer,
  minArea: number,
): PixelRegion[] {
  const visited = new Uint8Array(mask.length);
  const regions: PixelRegion[] = [];

  const offsets = [
    { dx: 1, dy: 0 },
    { dx: -1, dy: 0 },
    { dx: 0, dy: 1 },
    { dx: 0, dy: -1 },
  ];

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * width + x;
      if (mask[index] === 0 || visited[index] === 1) {
        continue;
      }

      const stack = [index];
      visited[index] = 1;
      let minX = x;
      let minY = y;
      let maxX = x;
      let maxY = y;
      let area = 0;
      let sumOld = 0;
      let sumNew = 0;

      while (stack.length) {
        const current = stack.pop() as number;
        const cx = current % width;
        const cy = Math.floor(current / width);
        area += 1;
        if (cx < minX) minX = cx;
        if (cx > maxX) maxX = cx;
        if (cy < minY) minY = cy;
        if (cy > maxY) maxY = cy;
        sumOld += oldPixels.data[current];
        sumNew += newPixels.data[current];

        for (const { dx, dy } of offsets) {
          const nx = cx + dx;
          const ny = cy + dy;
          if (nx < 0 || nx >= width || ny < 0 || ny >= height) {
            continue;
          }
          const nIndex = ny * width + nx;
          if (mask[nIndex] === 0 || visited[nIndex] === 1) {
            continue;
          }
          visited[nIndex] = 1;
          stack.push(nIndex);
        }
      }

      if (area >= minArea) {
        regions.push({
          area,
          minX,
          minY,
          maxX: maxX + 1,
          maxY: maxY + 1,
          sumOld,
          sumNew,
        });
      }
    }
  }

  return regions;
}
