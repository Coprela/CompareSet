import { IInputs, IOutputs } from "./generated/ManifestTypes";

const DEFAULT_DPI = 200;
const DEFAULT_THRESHOLD = 36;
const MIN_DPI = 72;
const MAX_DPI = 600;
const MIN_THRESHOLD = 0;
const MAX_THRESHOLD = 765;

type ComparisonPayload = {
  oldBase64: string;
  newBase64: string;
  dpi: number;
  threshold: number;
};

type FileKind = "old" | "new";

type UIElements = {
  oldInput: HTMLInputElement;
  newInput: HTMLInputElement;
  oldName: HTMLSpanElement;
  newName: HTMLSpanElement;
  dpiInput: HTMLInputElement;
  thresholdInput: HTMLInputElement;
  compareButton: HTMLButtonElement;
  exportButton: HTMLButtonElement;
  status: HTMLDivElement;
  viewer: HTMLIFrameElement;
  placeholder: HTMLDivElement;
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
  private ui!: UIElements;
  private currentOldBase64: string | null = null;
  private currentNewBase64: string | null = null;
  private currentDpi = DEFAULT_DPI;
  private currentThreshold = DEFAULT_THRESHOLD;
  private manualMode = false;
  private oldFileName: string | null = null;
  private newFileName: string | null = null;

  public init(
    context: ComponentFramework.Context<IInputs>,
    notifyOutputChanged: () => void,
    _state: ComponentFramework.Dictionary,
    container: HTMLDivElement
  ): void {
    this.context = context;
    this.notifyOutputChanged = notifyOutputChanged;
    this.container = container;

    this.buildUi();
    this.setStatus("Envie dois PDFs para iniciar a comparação.");
    this.updateControlsState();
  }

  public updateView(context: ComponentFramework.Context<IInputs>): void {
    this.context = context;

    const oldBase64 = this.normalizeBase64(context.parameters.oldPdfBase64?.raw);
    const newBase64 = this.normalizeBase64(context.parameters.newPdfBase64?.raw);
    const dpi = this.normalizeNumber(context.parameters.dpi?.raw, DEFAULT_DPI, MIN_DPI, MAX_DPI);
    const threshold = this.normalizeNumber(context.parameters.threshold?.raw, DEFAULT_THRESHOLD, MIN_THRESHOLD, MAX_THRESHOLD);

    if (this.manualMode) {
      return;
    }

    this.currentDpi = dpi;
    this.currentThreshold = threshold;
    this.ui.dpiInput.value = String(this.currentDpi);
    this.ui.thresholdInput.value = String(this.currentThreshold);

    if (!oldBase64 || !newBase64) {
      this.currentOldBase64 = null;
      this.currentNewBase64 = null;
      this.oldFileName = null;
      this.newFileName = null;
      this.ui.oldInput.value = "";
      this.ui.newInput.value = "";
      this.ui.oldName.textContent = "Nenhum arquivo selecionado";
      this.ui.newName.textContent = "Nenhum arquivo selecionado";
      this.resetState();
      this.setStatus("Envie dois PDFs para iniciar a comparação.");
      this.updateControlsState();
      return;
    }

    this.currentOldBase64 = oldBase64;
    this.currentNewBase64 = newBase64;
    this.oldFileName = "pdf-antigo";
    this.newFileName = "pdf-novo";
    this.ui.oldName.textContent = "PDF fornecido via parâmetro";
    this.ui.newName.textContent = "PDF fornecido via parâmetro";
    this.updateControlsState();

    const payload: ComparisonPayload = {
      oldBase64,
      newBase64,
      dpi: this.currentDpi,
      threshold: this.currentThreshold
    };

    this.requestComparison(payload);
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

  private buildUi(): void {
    this.container.className = "cs-viewer-root";
    this.container.textContent = "";

    const uploads = document.createElement("div");
    uploads.className = "cs-viewer-uploads";

    const oldGroup = document.createElement("div");
    oldGroup.className = "cs-viewer-upload";
    const oldLabel = document.createElement("label");
    oldLabel.className = "cs-viewer-label";
    oldLabel.textContent = "PDF antigo";
    const oldInput = document.createElement("input");
    oldInput.type = "file";
    oldInput.accept = "application/pdf";
    oldInput.className = "cs-viewer-file-input";
    const oldName = document.createElement("span");
    oldName.className = "cs-viewer-file-name";
    oldName.textContent = "Nenhum arquivo selecionado";
    oldGroup.append(oldLabel, oldInput, oldName);

    const newGroup = document.createElement("div");
    newGroup.className = "cs-viewer-upload";
    const newLabel = document.createElement("label");
    newLabel.className = "cs-viewer-label";
    newLabel.textContent = "PDF novo";
    const newInput = document.createElement("input");
    newInput.type = "file";
    newInput.accept = "application/pdf";
    newInput.className = "cs-viewer-file-input";
    const newName = document.createElement("span");
    newName.className = "cs-viewer-file-name";
    newName.textContent = "Nenhum arquivo selecionado";
    newGroup.append(newLabel, newInput, newName);

    uploads.append(oldGroup, newGroup);

    const actions = document.createElement("div");
    actions.className = "cs-viewer-actions";

    const dpiGroup = document.createElement("div");
    dpiGroup.className = "cs-viewer-setting";
    const dpiLabel = document.createElement("label");
    dpiLabel.className = "cs-viewer-label";
    dpiLabel.textContent = "DPI";
    const dpiInput = document.createElement("input");
    dpiInput.type = "number";
    dpiInput.min = String(MIN_DPI);
    dpiInput.max = String(MAX_DPI);
    dpiInput.value = String(this.currentDpi);
    dpiInput.className = "cs-viewer-number";
    dpiGroup.append(dpiLabel, dpiInput);

    const thresholdGroup = document.createElement("div");
    thresholdGroup.className = "cs-viewer-setting";
    const thresholdLabel = document.createElement("label");
    thresholdLabel.className = "cs-viewer-label";
    thresholdLabel.textContent = "Limite";
    const thresholdInput = document.createElement("input");
    thresholdInput.type = "number";
    thresholdInput.min = String(MIN_THRESHOLD);
    thresholdInput.max = String(MAX_THRESHOLD);
    thresholdInput.value = String(this.currentThreshold);
    thresholdInput.className = "cs-viewer-number";
    thresholdGroup.append(thresholdLabel, thresholdInput);

    const compareButton = document.createElement("button");
    compareButton.type = "button";
    compareButton.className = "cs-viewer-button";
    compareButton.textContent = "Comparar PDFs";

    const exportButton = document.createElement("button");
    exportButton.type = "button";
    exportButton.className = "cs-viewer-button cs-viewer-button--primary";
    exportButton.textContent = "Exportar resultado";
    exportButton.disabled = true;

    actions.append(dpiGroup, thresholdGroup, compareButton, exportButton);

    const status = document.createElement("div");
    status.className = "cs-viewer-status";
    status.textContent = "";

    const preview = document.createElement("div");
    preview.className = "cs-viewer-preview";
    const viewer = document.createElement("iframe");
    viewer.className = "cs-viewer-frame";
    viewer.title = "Resultado da comparação";
    viewer.setAttribute("sandbox", "allow-scripts allow-same-origin allow-downloads");
    viewer.src = "about:blank";
    const placeholder = document.createElement("div");
    placeholder.className = "cs-viewer-placeholder";
    placeholder.textContent = "O PDF resultante aparecerá aqui após a comparação.";
    preview.append(viewer, placeholder);

    this.container.append(uploads, actions, status, preview);

    oldInput.addEventListener("change", () => {
      void this.handleFileChange("old");
    });
    newInput.addEventListener("change", () => {
      void this.handleFileChange("new");
    });
    dpiInput.addEventListener("change", () => {
      this.handleSettingsChange();
    });
    thresholdInput.addEventListener("change", () => {
      this.handleSettingsChange();
    });
    compareButton.addEventListener("click", () => {
      this.manualMode = true;
      this.triggerComparisonFromState();
    });
    exportButton.addEventListener("click", () => {
      this.handleExportClick();
    });

    this.ui = {
      oldInput,
      newInput,
      oldName,
      newName,
      dpiInput,
      thresholdInput,
      compareButton,
      exportButton,
      status,
      viewer,
      placeholder
    };
  }

  private async handleFileChange(kind: FileKind): Promise<void> {
    const input = kind === "old" ? this.ui.oldInput : this.ui.newInput;
    const file = input.files?.[0] ?? null;

    if (!file) {
      this.setFileState(kind, null, null);
      if (!this.hasReadyPayload()) {
        this.resetState();
        this.setStatus("Envie dois PDFs para iniciar a comparação.");
      }
      this.updateControlsState();
      return;
    }

    if (file.type && file.type !== "application/pdf") {
      input.value = "";
      this.setStatus("Selecione um arquivo PDF válido.");
      return;
    }

    this.manualMode = true;
    this.setStatus(`Carregando ${kind === "old" ? "PDF antigo" : "PDF novo"}...`);

    try {
      const base64 = await this.readFileAsBase64(file);
      this.setFileState(kind, base64, file.name);
      this.updateControlsState();
      this.triggerComparisonFromState();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Falha ao ler o arquivo.";
      this.setStatus(`Erro: ${message}`);
      console.error("[CompareSet]", message);
    }
  }

  private setFileState(kind: FileKind, base64: string | null, fileName: string | null): void {
    if (kind === "old") {
      this.currentOldBase64 = base64;
      this.oldFileName = fileName;
      this.ui.oldName.textContent = fileName ?? "Nenhum arquivo selecionado";
    } else {
      this.currentNewBase64 = base64;
      this.newFileName = fileName;
      this.ui.newName.textContent = fileName ?? "Nenhum arquivo selecionado";
    }
  }

  private handleSettingsChange(): void {
    this.manualMode = true;
    const dpiValue = Number.parseInt(this.ui.dpiInput.value, 10);
    const thresholdValue = Number.parseInt(this.ui.thresholdInput.value, 10);

    this.currentDpi = this.normalizeNumber(dpiValue, DEFAULT_DPI, MIN_DPI, MAX_DPI);
    this.currentThreshold = this.normalizeNumber(thresholdValue, DEFAULT_THRESHOLD, MIN_THRESHOLD, MAX_THRESHOLD);

    this.ui.dpiInput.value = String(this.currentDpi);
    this.ui.thresholdInput.value = String(this.currentThreshold);

    if (this.hasReadyPayload()) {
      this.triggerComparisonFromState();
    } else {
      this.updateControlsState();
    }
  }

  private triggerComparisonFromState(): void {
    const payload = this.buildPayloadFromState();
    if (!payload) {
      this.updateControlsState();
      return;
    }

    this.requestComparison(payload);
  }

  private buildPayloadFromState(): ComparisonPayload | null {
    if (!this.currentOldBase64 || !this.currentNewBase64) {
      return null;
    }

    return {
      oldBase64: this.currentOldBase64,
      newBase64: this.currentNewBase64,
      dpi: this.currentDpi,
      threshold: this.currentThreshold
    };
  }

  private requestComparison(payload: ComparisonPayload): void {
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

  private startComparison(payload: ComparisonPayload): void {
    this.setBusy(true);
    this.lastRequested = payload;
    this.pendingRequest = null;
    this.setDiff(undefined);
    this.setStatus("Preparando comparação...");

    try {
      const oldBytes = this.decodeBase64(payload.oldBase64);
      const newBytes = this.decodeBase64(payload.newBase64);
      const oldBuffer = oldBytes.buffer.slice(0);
      const newBuffer = newBytes.buffer.slice(0);

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
      const message = error instanceof Error ? error.message : "Erro desconhecido ao preparar os PDFs.";
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
    this.updateViewer(value);
    this.updateControlsState();
    this.notifyOutputChanged();
  }

  private updateViewer(base64: string | undefined): void {
    if (!this.ui) {
      return;
    }

    if (base64) {
      const url = `data:application/pdf;base64,${base64}`;
      this.ui.viewer.src = url;
      this.ui.placeholder.classList.add("cs-viewer-placeholder--hidden");
    } else {
      this.ui.viewer.src = "about:blank";
      this.ui.placeholder.classList.remove("cs-viewer-placeholder--hidden");
    }
  }

  private setStatus(value: string | undefined): void {
    if (this.statusMessage === value) {
      return;
    }

    this.statusMessage = value;
    if (this.ui) {
      this.ui.status.textContent = value ?? "";
    }
    this.notifyOutputChanged();
  }

  private setBusy(value: boolean): void {
    if (this.busy === value) {
      return;
    }

    this.busy = value;
    this.updateControlsState();
    this.setProcessingOutput(value);
  }

  private setProcessingOutput(value: boolean): void {
    if (this.isProcessing === value) {
      return;
    }

    this.isProcessing = value;
    this.notifyOutputChanged();
  }

  private updateControlsState(): void {
    if (!this.ui) {
      return;
    }

    const hasPayload = this.hasReadyPayload();
    this.ui.compareButton.disabled = this.busy || !hasPayload;
    this.ui.exportButton.disabled = !this.diffPdfBase64;
    this.ui.oldInput.disabled = this.busy;
    this.ui.newInput.disabled = this.busy;
    this.container.classList.toggle("cs-viewer--busy", this.busy);
  }

  private hasReadyPayload(): boolean {
    return Boolean(this.currentOldBase64 && this.currentNewBase64);
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

  private normalizeNumber(value: number | null | undefined, fallback: number, min: number, max: number): number {
    if (typeof value === "number" && Number.isFinite(value)) {
      const clamped = Math.min(Math.max(Math.round(value), min), max);
      return clamped;
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

  private async readFileAsBase64(file: File): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result;
        if (result instanceof ArrayBuffer) {
          resolve(this.bytesToBase64(new Uint8Array(result)));
        } else {
          reject(new Error("Não foi possível ler o arquivo."));
        }
      };
      reader.onerror = () => {
        reject(reader.error ?? new Error("Não foi possível ler o arquivo."));
      };
      reader.readAsArrayBuffer(file);
    });
  }

  private bytesToBase64(bytes: Uint8Array): string {
    let binary = "";
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
      const sub = bytes.subarray(index, index + chunkSize);
      binary += String.fromCharCode.apply(null, Array.from(sub) as number[]);
    }
    return btoa(binary);
  }

  private handleExportClick(): void {
    if (!this.diffPdfBase64) {
      return;
    }

    const link = document.createElement("a");
    link.href = `data:application/pdf;base64,${this.diffPdfBase64}`;
    link.download = this.buildExportFileName();
    link.rel = "noopener";
    document.body.append(link);
    link.click();
    link.remove();
  }

  private buildExportFileName(): string {
    const oldSegment = this.sanitizeFileNameSegment(this.oldFileName ?? "antigo");
    const newSegment = this.sanitizeFileNameSegment(this.newFileName ?? "novo");
    return `CompareSet_${oldSegment}_vs_${newSegment}.pdf`;
  }

  private sanitizeFileNameSegment(value: string): string {
    const withoutExtension = value.replace(/\.pdf$/i, "");
    const sanitized = withoutExtension.replace(/[^a-z0-9_-]+/gi, "-");
    return sanitized || "documento";
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
