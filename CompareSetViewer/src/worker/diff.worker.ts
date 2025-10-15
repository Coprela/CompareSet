import { PDFDocument } from "pdf-lib";
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist/types/src/display/api";
import UPNG from "upng-js";

(GlobalWorkerOptions as any).workerSrc = undefined as any;

const ctx: DedicatedWorkerGlobalScope = self as unknown as DedicatedWorkerGlobalScope;

ctx.onmessage = async (event: MessageEvent<DiffWorkerRequest>) => {
  const payload = event.data;
  if (!payload) {
    return;
  }

  try {
    sendStatus("Carregando PDFs...");
    const { oldPdf, newPdf, dpi, threshold } = payload;

    const [oldProxy, newProxy] = await Promise.all([
      loadPdf(oldPdf),
      loadPdf(newPdf)
    ]);

    const totalPages = Math.min(oldProxy.numPages, newProxy.numPages);
    if (totalPages === 0) {
      throw new Error("PDFs sem páginas.");
    }

    const [oldLibDoc, newLibDoc, outDoc] = await Promise.all([
      PDFDocument.load(oldPdf),
      PDFDocument.load(newPdf),
      PDFDocument.create()
    ]);

    for (let index = 1; index <= totalPages; index += 1) {
      sendStatus(`Processando página ${index} de ${totalPages}...`);

      const [oldPageProxy, newPageProxy] = await Promise.all([
        oldProxy.getPage(index),
        newProxy.getPage(index)
      ]);

      const oldRender = await renderPage(oldPageProxy, dpi);
      const newRender = await renderPage(newPageProxy, dpi);

      // Padronizamos os buffers para a maior dimensão encontrada entre as páginas
      // para evitar recortes quando os PDFs possuem tamanhos diferentes.
      const targetWidth = Math.max(oldRender.width, newRender.width);
      const targetHeight = Math.max(oldRender.height, newRender.height);
      const normalizedOld = normalizeRender(oldRender, targetWidth, targetHeight);
      const normalizedNew = normalizeRender(newRender, targetWidth, targetHeight);

      const overlays = buildOverlays(normalizedOld.data, normalizedNew.data, threshold);

      const [oldPage] = await outDoc.copyPages(oldLibDoc, [index - 1]);
      const [newPage] = await outDoc.copyPages(newLibDoc, [index - 1]);

      if (overlays.redPixels > 0) {
        const redPngBuffer = UPNG.encode([new Uint8Array(overlays.red)], targetWidth, targetHeight, 0);
        const redImage = await outDoc.embedPng(new Uint8Array(redPngBuffer));
        oldPage.drawImage(redImage, {
          x: 0,
          y: 0,
          width: oldPage.getWidth(),
          height: oldPage.getHeight()
        });
      }

      if (overlays.greenPixels > 0) {
        const greenPngBuffer = UPNG.encode([new Uint8Array(overlays.green)], targetWidth, targetHeight, 0);
        const greenImage = await outDoc.embedPng(new Uint8Array(greenPngBuffer));
        newPage.drawImage(greenImage, {
          x: 0,
          y: 0,
          width: newPage.getWidth(),
          height: newPage.getHeight()
        });
      }

      outDoc.addPage(oldPage);
      outDoc.addPage(newPage);
    }

    await Promise.all([oldProxy.cleanup(), newProxy.cleanup()]);

    const pdfBytes = await outDoc.save();
    const base64 = uint8ToBase64(pdfBytes);
    sendStatus("Concluído.");
    ctx.postMessage({ type: "result", base64 } satisfies DiffWorkerSuccess);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Erro inesperado.";
    ctx.postMessage({ type: "error", message } satisfies DiffWorkerError);
  }
};

async function loadPdf(data: ArrayBuffer): Promise<PDFDocumentProxy> {
  const task = getDocument({ data });
  return task.promise;
}

async function renderPage(page: PDFPageProxy, dpi: number): Promise<{ data: Uint8ClampedArray; width: number; height: number; }> {
  const scale = dpi / 72;
  const viewport = page.getViewport({ scale });
  const canvas = new OffscreenCanvas(viewport.width, viewport.height);
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) {
    throw new Error("Contexto do canvas indisponível.");
  }

  await page.render({ canvasContext: context, viewport }).promise;
  const width = canvas.width;
  const height = canvas.height;
  const imageData = context.getImageData(0, 0, width, height);
  return { data: imageData.data, width, height };
}

function buildOverlays(oldData: Uint8ClampedArray, newData: Uint8ClampedArray, threshold: number): { red: Uint8ClampedArray; green: Uint8ClampedArray; redPixels: number; greenPixels: number; } {
  const length = oldData.length;
  const red = new Uint8ClampedArray(length);
  const green = new Uint8ClampedArray(length);
  let redPixels = 0;
  let greenPixels = 0;

  for (let i = 0; i < length; i += 4) {
    const oldR = oldData[i];
    const oldG = oldData[i + 1];
    const oldB = oldData[i + 2];
    const oldA = oldData[i + 3] / 255;

    const newR = newData[i];
    const newG = newData[i + 1];
    const newB = newData[i + 2];
    const newA = newData[i + 3] / 255;

    const diff = Math.abs(oldR - newR) + Math.abs(oldG - newG) + Math.abs(oldB - newB);
    if (diff <= threshold) {
      continue;
    }

    const oldPresence = (oldR + oldG + oldB) * oldA;
    const newPresence = (newR + newG + newB) * newA;

    if (oldPresence > newPresence) {
      red[i] = 255;
      red[i + 1] = 0;
      red[i + 2] = 0;
      red[i + 3] = 180;
      redPixels += 1;
    } else {
      green[i] = 0;
      green[i + 1] = 200;
      green[i + 2] = 0;
      green[i + 3] = 180;
      greenPixels += 1;
    }
  }

  return { red, green, redPixels, greenPixels };
}

function normalizeRender(render: { data: Uint8ClampedArray; width: number; height: number; }, width: number, height: number): { data: Uint8ClampedArray; width: number; height: number; } {
  if (render.width === width && render.height === height) {
    return render;
  }

  const padded = new Uint8ClampedArray(width * height * 4);
  const copyWidth = Math.min(render.width, width);
  const copyHeight = Math.min(render.height, height);

  for (let y = 0; y < copyHeight; y += 1) {
    const srcStart = y * render.width * 4;
    const dstStart = y * width * 4;
    padded.set(render.data.subarray(srcStart, srcStart + copyWidth * 4), dstStart);
  }

  return { data: padded, width, height };
}

function uint8ToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    const sub = bytes.subarray(i, i + chunk);
    binary += String.fromCharCode.apply(null, Array.from(sub));
  }
  return btoa(binary);
}

function sendStatus(message: string): void {
  ctx.postMessage({ type: "status", message } satisfies DiffWorkerProgress);
}
