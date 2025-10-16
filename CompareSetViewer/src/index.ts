import { IInputs, IOutputs } from "./generated/ManifestTypes";
import type { CompareConfig, CompareResult, ProgressMessage } from "./types";

const DEFAULT_DPI = 144;
const DEFAULT_GRID = 10;
const DEFAULT_THRESHOLD = 18;
const DEFAULT_MIN_AREA = 64;
const DEFAULT_STROKE_WIDTH = 0.8;
const DEFAULT_ALPHA = 0.25;
const DEFAULT_REMOVED = "#FF0000";
const DEFAULT_ADDED = "#00AA00";
const RUN_DEBOUNCE_MS = 250;

type WorkerInstance = Worker & {
  terminate(): void;
};

export class CompareSetViewer implements ComponentFramework.StandardControl<IInputs, IOutputs> {
  private container!: HTMLDivElement;
  private notifyOutputChanged!: () => void;
  private context!: ComponentFramework.Context<IInputs>;
  private worker: WorkerInstance | null = null;
  private debounceHandle: number | null = null;
  private latestInputs: CompareConfig | null = null;
  private lastRunInputsKey: string | null = null;
  private lastRunCompareFlag = false;
  private outputs: CompareResult = {
    outputPdfBase64: null,
    diffSummaryJson: null,
    diffCount: 0,
    status: "Idle",
  };

  public init(
    context: ComponentFramework.Context<IInputs>,
    notifyOutputChanged: () => void,
    _state: ComponentFramework.Dictionary,
    container: HTMLDivElement,
  ): void {
    this.context = context;
    this.notifyOutputChanged = notifyOutputChanged;
    this.container = container;
    this.container.className = "cs-engine";
    this.container.textContent = "CompareSet Viewer engine running.";

    this.ensureWorker();
    this.applyInputs(context);
  }

  public updateView(context: ComponentFramework.Context<IInputs>): void {
    this.context = context;
    this.applyInputs(context);
  }

  public getOutputs(): IOutputs {
    return {
      outputPdfBase64: this.outputs.outputPdfBase64,
      diffSummaryJson: this.outputs.diffSummaryJson,
      diffCount: this.outputs.diffCount,
      status: this.outputs.status,
    };
  }

  public destroy(): void {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
    }
    if (this.debounceHandle !== null) {
      clearTimeout(this.debounceHandle);
      this.debounceHandle = null;
    }
  }

  private ensureWorker(): void {
    if (!this.worker) {
      this.worker = new Worker(new URL("./worker/compareWorker.ts", import.meta.url), { type: "module" });
      this.worker.onmessage = (event: MessageEvent) => {
        const message = event.data as ProgressMessage | CompareResult;
        if ("type" in message) {
          this.outputs.status = message.text;
          this.notifyOutputChanged();
        } else {
          this.outputs = message;
          this.notifyOutputChanged();
        }
      };
      this.worker.onerror = (error) => {
        this.outputs.status = `Error: ${error.message}`;
        this.notifyOutputChanged();
      };
    }
  }

  private applyInputs(context: ComponentFramework.Context<IInputs>): void {
    const cfg = this.buildConfig(context);
    this.latestInputs = cfg;

    const runRequested = context.parameters.runCompare.raw === true;
    if (runRequested && !this.lastRunCompareFlag) {
      this.lastRunCompareFlag = true;
      this.triggerCompare();
      return;
    }

    if (!runRequested) {
      this.lastRunCompareFlag = false;
    }

    const key = this.hashInputs(cfg);
    if (this.lastRunInputsKey !== key) {
      this.scheduleCompare();
    }
  }

  private scheduleCompare(): void {
    if (this.debounceHandle !== null) {
      clearTimeout(this.debounceHandle);
    }
    this.debounceHandle = window.setTimeout(() => {
      this.debounceHandle = null;
      this.triggerCompare();
    }, RUN_DEBOUNCE_MS);
  }

  private triggerCompare(): void {
    if (!this.latestInputs) {
      return;
    }
    if (!this.latestInputs.oldPdfBase64 || !this.latestInputs.newPdfBase64) {
      this.outputs = {
        outputPdfBase64: null,
        diffSummaryJson: null,
        diffCount: 0,
        status: "Waiting for both PDFs...",
      };
      this.notifyOutputChanged();
      return;
    }

    this.ensureWorker();
    if (!this.worker) {
      this.outputs.status = "Worker unavailable.";
      this.notifyOutputChanged();
      return;
    }

    this.outputs.status = "Starting comparison...";
    this.outputs.outputPdfBase64 = null;
    this.outputs.diffSummaryJson = null;
    this.outputs.diffCount = 0;
    this.notifyOutputChanged();

    this.lastRunInputsKey = this.hashInputs(this.latestInputs);
    this.worker.postMessage({ type: "compare", payload: this.latestInputs });
  }

  private buildConfig(context: ComponentFramework.Context<IInputs>): CompareConfig {
    const safeNumber = (
      value: number | null | undefined,
      fallback: number,
      min: number,
      max: number,
    ): number => {
      if (typeof value !== "number" || Number.isNaN(value)) {
        return fallback;
      }
      return Math.min(Math.max(value, min), max);
    };

    const clampAlpha = (value: number | null | undefined): number => {
      if (typeof value !== "number" || Number.isNaN(value)) {
        return DEFAULT_ALPHA;
      }
      return Math.min(Math.max(value, 0), 1);
    };

    const normalizeColor = (value: string | null | undefined, fallback: string): string => {
      if (typeof value !== "string" || !/^#?[0-9a-fA-F]{6}$/.test(value.trim())) {
        return fallback;
      }
      return value.startsWith("#") ? value : `#${value}`;
    };

    return {
      oldPdfBase64: context.parameters.oldPdfBase64.raw ?? "",
      newPdfBase64: context.parameters.newPdfBase64.raw ?? "",
      dpi: safeNumber(context.parameters.dpi.raw, DEFAULT_DPI, 72, 600),
      gridRows: safeNumber(context.parameters.gridRows.raw, DEFAULT_GRID, 1, 100),
      gridCols: safeNumber(context.parameters.gridCols.raw, DEFAULT_GRID, 1, 100),
      diffThreshold: safeNumber(context.parameters.diffThreshold.raw, DEFAULT_THRESHOLD, 0, 255),
      minRegionArea: safeNumber(context.parameters.minRegionArea.raw, DEFAULT_MIN_AREA, 1, 1_000_000),
      strokeWidthPt: safeNumber(context.parameters.strokeWidthPt.raw, DEFAULT_STROKE_WIDTH, 0.1, 10),
      overlayAlpha: clampAlpha(context.parameters.overlayAlpha.raw),
      colorRemoved: normalizeColor(context.parameters.colorRemoved.raw, DEFAULT_REMOVED),
      colorAdded: normalizeColor(context.parameters.colorAdded.raw, DEFAULT_ADDED),
    };
  }

  private hashInputs(config: CompareConfig): string {
    return JSON.stringify([
      config.oldPdfBase64?.slice(0, 24),
      config.newPdfBase64?.slice(0, 24),
      config.dpi,
      config.gridRows,
      config.gridCols,
      config.diffThreshold,
      config.minRegionArea,
      config.strokeWidthPt,
      config.overlayAlpha,
      config.colorRemoved,
      config.colorAdded,
    ]);
  }
}

export default CompareSetViewer;
