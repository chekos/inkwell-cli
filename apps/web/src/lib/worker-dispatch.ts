import { isWorkerDispatchEnabled } from "@/lib/env";

export interface DispatchPayload {
  jobId: string;
  userId: string;
  url: string;
}

export interface DispatchResult {
  dispatched: boolean;
  workerRunId?: string;
  reason?: string;
}

export async function dispatchImportJob(payload: DispatchPayload): Promise<DispatchResult> {
  const endpoint = process.env.INKWELL_WORKER_ENDPOINT;
  const token = process.env.INKWELL_WORKER_TOKEN;

  if (!isWorkerDispatchEnabled()) {
    return { dispatched: false, reason: "Worker dispatch is disabled." };
  }

  if (!endpoint) {
    return { dispatched: false, reason: "INKWELL_WORKER_ENDPOINT is missing." };
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    return {
      dispatched: false,
      reason: `Worker returned ${response.status}.`,
    };
  }

  const body = (await response.json().catch(() => ({}))) as { workerRunId?: string };
  return { dispatched: true, workerRunId: body.workerRunId };
}
