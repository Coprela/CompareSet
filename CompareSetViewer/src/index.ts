import { IInputs, IOutputs } from "./generated/ManifestTypes";

const DEFAULT_DPI = 200;
const DEFAULT_THRESHOLD = 36;

export class CompareSetViewer implements ComponentFramework.StandardControl<IInputs, IOutputs> {
  private container!: HTMLDivElement;
  private statusEl!: HTMLDivElement;
  private oldInput!: HTMLInputElement;
  private newInput!: HTMLInputElement;
  private compareButton!: HTMLButtonElement;
  private exportButton!: HTMLButtonElement;
  private iframe!: HTMLIFrameElement;

  private context!: ComponentFramework.Context<IInputs>;
  private notifyOutputChanged!: () => void;
  private diffPdfBase64: string | undefined;
  private worker: Worker | undefined;
  private busy = false;

  public init(context: ComponentFramework.Context<IInputs>, notifyOutputChanged: () => void, state: ComponentFramework.Dictionary, container: HTMLDivElement): void {
    this.context = context;
    this.notifyOutputChanged = notifyOutputChanged;
    this.container = container;

    this.container.classList.add("cs-root");

    const header = document.createElement("div");
    header.className = "cs-header";
    header.textContent = "CompareSet Viewer";

    const toolbar = document.createElement("div");
    toolbar.className = "cs-toolbar";

    const oldWrapper = document.createElement("label");
    oldWrapper.className = "cs-file";
    oldWrapper.textContent = "PDF Antigo";

    this.oldInput = document.createElement("input");
    this.oldInput.type = "file";
    this.oldInput.accept = "application/pdf";
    this.oldInput.addEventListener("change", () => {
      if (this.oldInput.files && this.oldInput.files.length > 0) {
        this.pushStatus("PDF Antigo selecionado.");
      }
      this.updateButtons();
    });
    oldWrapper.appendChild(this.oldInput);

    const newWrapper = document.createElement("label");
    newWrapper.className = "cs-file";
    newWrapper.textContent = "PDF Novo";

    this.newInput = document.createElement("input");
    this.newInput.type = "file";
    this.newInput.accept = "application/pdf";
    this.newInput.addEventListener("change", () => {
      if (this.newInput.files && this.newInput.files.length > 0) {
        this.pushStatus("PDF Novo selecionado.");
      }
      this.updateButtons();
    });
    newWrapper.appendChild(this.newInput);

    this.compareButton = document.createElement("button");
    this.compareButton.textContent = "Comparar";
    this.compareButton.addEventListener("click", () => void this.handleCompare());

    this.exportButton = document.createElement("button");
    this.exportButton.textContent = "Exportar PDF";
    this.exportButton.className = "secondary";
    this.exportButton.addEventListener("click", () => this.handleExport());

    const buttonRow = document.createElement("div");
    buttonRow.className = "cs-buttons";
    buttonRow.appendChild(this.compareButton);
    buttonRow.appendChild(this.exportButton);

    toolbar.appendChild(oldWrapper);
    toolbar.appendChild(newWrapper);
    toolbar.appendChild(buttonRow);

    this.statusEl = document.createElement("div");
    this.statusEl.className = "cs-status";

    this.iframe = document.createElement("iframe");
    this.iframe.className = "cs-iframe";
    this.iframe.setAttribute("title", "Resultado da comparação de PDFs");

    this.container.appendChild(header);
    this.container.appendChild(toolbar);
    this.container.appendChild(this.statusEl);
    this.container.appendChild(this.iframe);

    this.updateButtons();
  }

  public updateView(context: ComponentFramework.Context<IInputs>): void {
    this.context = context;
  }

  public getOutputs(): IOutputs {
    return {
      diffPdfBase64: this.diffPdfBase64 ?? null
    };
  }

  public destroy(): void {
    if (this.worker) {
      this.worker.terminate();
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
          this.pushStatus(payload.message);
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

  private async handleCompare(): Promise<void> {
    if (this.busy) {
      return;
    }
    const oldFile = this.oldInput.files?.[0];
    const newFile = this.newInput.files?.[0];
    if (!oldFile || !newFile) {
      this.pushStatus("Selecione ambos os PDFs antes de comparar.");
      return;
    }

    this.busy = true;
    this.diffPdfBase64 = undefined;
    if (this.iframe) {
      this.iframe.src = "about:blank";
    }
    this.updateButtons();
    this.pushStatus("Preparando arquivos...");

    try {
      const backendMode = (this.context as Record<string, unknown>)?.parameters
        && (this.context as Record<string, any>).parameters.apiMode?.raw;
      if (backendMode === "backend-api") {
        this.pushStatus("Modo backend-api ainda não disponível nesta versão.");
        this.busy = false;
        this.updateButtons();
        return;
      }

      const [oldBuffer, newBuffer] = await Promise.all([oldFile.arrayBuffer(), newFile.arrayBuffer()]);
      const dpi = this.context.parameters.dpi?.raw ?? DEFAULT_DPI;
      const threshold = this.context.parameters.threshold?.raw ?? DEFAULT_THRESHOLD;

      const worker = this.getWorker();
      worker.postMessage({
        oldPdf: oldBuffer,
        newPdf: newBuffer,
        dpi,
        threshold
      } satisfies DiffWorkerRequest, [oldBuffer, newBuffer]);
      this.pushStatus("Iniciando comparação...");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Erro desconhecido ao ler arquivos.";
      this.handleWorkerError(message);
    }
  }

  private handleWorkerResult(base64: string): void {
    this.busy = false;
    this.diffPdfBase64 = base64;
    this.updateButtons();
    this.notifyOutputChanged();

    const dataUrl = `data:application/pdf;base64,${base64}`;
    this.iframe.src = dataUrl;
  }

  private handleWorkerError(message: string): void {
    this.busy = false;
    this.updateButtons();
    this.pushStatus(`Erro: ${message}`);
  }

  private handleExport(): void {
    if (!this.diffPdfBase64) {
      this.pushStatus("Nenhum PDF de diferença disponível.");
      return;
    }
    const a = document.createElement("a");
    a.href = `data:application/pdf;base64,${this.diffPdfBase64}`;
    a.download = "CompareSetDiff.pdf";
    a.click();
  }

  private updateButtons(): void {
    const hasFiles = Boolean(this.oldInput?.files?.length && this.newInput?.files?.length);
    if (this.compareButton) {
      this.compareButton.disabled = !hasFiles || this.busy;
    }
    if (this.exportButton) {
      this.exportButton.disabled = !this.diffPdfBase64 || this.busy;
    }
  }

  private pushStatus(message: string): void {
    if (this.statusEl) {
      const now = new Date();
      const time = now.toLocaleTimeString();
      this.statusEl.textContent = `[${time}] ${message}`;
    }
  }
}

export default CompareSetViewer;
