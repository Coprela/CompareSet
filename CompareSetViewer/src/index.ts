import { IInputs, IOutputs } from "./generated/ManifestTypes";

const DEFAULT_DPI = 200;
const DEFAULT_THRESHOLD = 36;

type ComparisonPayload = {
  oldBase64: string;
  newBase64: string;
  dpi: number;
  threshold: number;
};

export class CompareSetViewer implements ComponentFramework.StandardControl<IInputs, IOutputs> {
  private container!: HTMLDivElement;
  private context!: ComponentFramework.Context<IInputs>;
  private notifyOutputChanged!: () => void;
  private worker: Worker | undefined;
  private diffPdfBase64: string | undefined;
  private busy = false;
  private pendingRequest: ComparisonPayload | null = null;
  private lastProcessed: ComparisonPayload | null = null;
  private lastRequested: ComparisonPayload | null = null;
  private statusMessage: string | undefined;
  private isProcessing = false;

  public init(
    context: ComponentFramework.Context<IInputs>,
    notifyOutputChanged: () => void,
    _state: ComponentFramework.Dictionary,
    container: HTMLDivElement
  ): void {
    this.context = context;
    this.notifyOutputChanged = notifyOutputChanged;
    this.container = container;

    this.container.classList.add("cs-motor-root");
    this.container.textContent = "";
  }

  public updateView(context: ComponentFramework.Context<IInputs>): void {
    this.context = context;

    const oldBase64 = this.normalizeBase64(context.parameters.oldPdfBase64?.raw);
    const newBase64 = this.normalizeBase64(context.parameters.newPdfBase64?.raw);
    const dpi = this.normalizeNumber(context.parameters.dpi?.raw, DEFAULT_DPI);
    const threshold = this.normalizeNumber(context.parameters.threshold?.raw, DEFAULT_THRESHOLD);

    if (!oldBase64 || !newBase64) {
      this.resetState();
      this.setStatus("Aguardando PDFs base64.");
      return;
    }

    const payload: ComparisonPayload = { oldBase64, newBase64, dpi, threshold };

    if (this.diffPdfBase64 && this.isSamePayload(this.lastProcessed, payload)) {
      return;
    }

    if (this.busy && this.isSamePayload(this.lastRequested, payload)) {
      return;
    }

    if (this.busy) {
      this.pendingRequest = payload;
      return;
    }

    this.startComparison(payload);
  }

  public getOutputs(): IOutputs {
    return {
      diffPdfBase64: this.diffPdfBase64 ?? null,
      statusMessage: this.statusMessage ?? null,
      isProcessing: this.isProcessing
    };
  }

  public destroy(): void {
    if (this.worker) {
      this.worker.terminate();
    }
  }

  private startComparison(payload: ComparisonPayload): void {
    this.setBusy(true);
    this.lastRequested = payload;
    this.pendingRequest = null;
    this.setDiff(undefined);
    this.setStatus("Preparando comparação...");

    try {
      const oldBytes = this.decodeBase64(payload.oldBase64);
      const newBytes = this.decodeBase64(payload.newBase64);
      const oldBuffer = oldBytes.buffer;
      const newBuffer = newBytes.buffer;

      const worker = this.getWorker();
      worker.postMessage(
        {
          oldPdf: oldBuffer,
          newPdf: newBuffer,
          dpi: payload.dpi,
          threshold: payload.threshold
        } satisfies DiffWorkerRequest,
        [oldBuffer, newBuffer]
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Erro desconhecido ao decodificar PDFs.";
      this.handleWorkerError(message);
    }
  }

  private getWorker(): Worker {
    if (!this.worker) {
      this.worker = new Worker(new URL("./worker/diff.worker.ts", import.meta.url), { type: "module" });
      this.worker.onmessage = (event: MessageEvent<DiffWorkerResponse>) => {
        const payload = event.data;
        if (!payload) {
          return;
        }

        if (payload.type === "status") {
          this.handleWorkerStatus(payload.message);
        } else if (payload.type === "result") {
          this.handleWorkerResult(payload.base64);
        } else if (payload.type === "error") {
          this.handleWorkerError(payload.message);
        }
      };

      this.worker.onerror = (error) => {
        this.handleWorkerError(error.message ?? "Erro desconhecido no processamento.");
      };
    }

    return this.worker;
  }

  private handleWorkerResult(base64: string): void {
    if (!this.lastRequested) {
      this.setBusy(false);
      this.flushPendingRequest();
      return;
    }

    this.setBusy(false);
    this.lastProcessed = this.lastRequested;
    this.lastRequested = null;
    this.setDiff(base64);
    this.setStatus("Comparação concluída.");
    this.flushPendingRequest();
  }

  private handleWorkerError(message: string): void {
    console.error(`[CompareSet] ${message}`);
    this.setBusy(false);
    this.lastRequested = null;
    this.setDiff(undefined);
    this.setStatus(`Erro: ${message}`);
    this.flushPendingRequest();
  }

  private flushPendingRequest(): void {
    if (!this.pendingRequest) {
      return;
    }

    const next = this.pendingRequest;
    this.pendingRequest = null;

    if (this.isSamePayload(this.lastProcessed, next)) {
      return;
    }

    if (this.busy) {
      this.pendingRequest = next;
      return;
    }

    this.startComparison(next);
  }

  private resetState(): void {
    this.pendingRequest = null;
    this.lastRequested = null;
    this.lastProcessed = null;
    this.setBusy(false);
    this.setDiff(undefined);
  }

  private setDiff(value: string | undefined): void {
    if (this.diffPdfBase64 === value) {
      return;
    }

    this.diffPdfBase64 = value;
    this.notifyOutputChanged();
  }

  private setStatus(value: string | undefined): void {
    if (this.statusMessage === value) {
      return;
    }

    this.statusMessage = value;
    this.notifyOutputChanged();
  }

  private setBusy(value: boolean): void {
    if (this.busy === value) {
      return;
    }

    this.busy = value;
    this.setProcessingOutput(value);
  }

  private setProcessingOutput(value: boolean): void {
    if (this.isProcessing === value) {
      return;
    }

    this.isProcessing = value;
    this.notifyOutputChanged();
  }

  private normalizeBase64(value?: string | null): string | null {
    if (!value) {
      return null;
    }

    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }

    const commaIndex = trimmed.indexOf(",");
    const base64 = commaIndex >= 0 ? trimmed.slice(commaIndex + 1) : trimmed;
    const sanitized = base64.replace(/\s+/g, "");
    return sanitized ? sanitized : null;
  }

  private normalizeNumber(value: number | null | undefined, fallback: number): number {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    return fallback;
  }

  private decodeBase64(base64: string): Uint8Array {
    const binary = atob(base64);
    const length = binary.length;
    const bytes = new Uint8Array(length);
    for (let index = 0; index < length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  private isSamePayload(source: ComparisonPayload | null, target: ComparisonPayload): boolean {
    return Boolean(
      source &&
      source.oldBase64 === target.oldBase64 &&
      source.newBase64 === target.newBase64 &&
      source.dpi === target.dpi &&
      source.threshold === target.threshold
    );
  }

  private handleWorkerStatus(message: string): void {
    console.info(`[CompareSet] ${message}`);
    this.setStatus(message);
  }
}

export default CompareSetViewer;
