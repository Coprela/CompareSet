declare module "*.worker.ts" {
  const DiffWorkerFactory: {
    new (): Worker;
  };
  export default DiffWorkerFactory;
}

declare interface DiffWorkerRequest {
  oldPdf: ArrayBuffer;
  newPdf: ArrayBuffer;
  dpi: number;
  threshold: number;
}

declare interface DiffWorkerProgress {
  type: "status";
  message: string;
  page?: number;
  totalPages?: number;
}

declare interface DiffWorkerSuccess {
  type: "result";
  base64: string;
}

declare interface DiffWorkerError {
  type: "error";
  message: string;
}

declare type DiffWorkerResponse = DiffWorkerProgress | DiffWorkerSuccess | DiffWorkerError;
