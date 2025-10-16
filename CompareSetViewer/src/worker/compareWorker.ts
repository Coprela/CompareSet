import { comparePdfs } from "../compare";
import type { CompareConfig, ProgressMessage, WorkerRequest, WorkerResponse } from "../types";

const ctx: DedicatedWorkerGlobalScope = self as unknown as DedicatedWorkerGlobalScope;

ctx.onmessage = async (event: MessageEvent<WorkerRequest>) => {
  const message = event.data;
  if (!message) {
    return;
  }
  if (message.type === "compare") {
    await handleCompare(message.payload);
  }
};

async function handleCompare(config: CompareConfig): Promise<void> {
  const progress = (update: ProgressMessage) => {
    ctx.postMessage(update satisfies WorkerResponse);
  };
  const result = await comparePdfs(config, progress);
  ctx.postMessage(result satisfies WorkerResponse);
}

export {}; // ensure module scope
