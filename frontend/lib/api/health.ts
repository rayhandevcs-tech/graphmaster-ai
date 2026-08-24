import { api } from "./client";

export interface ReadinessReport {
  status: string;
  [key: string]: unknown;
}

/** Both are public: an orchestrator probes them before any user exists. */
export const healthApi = {
  live: () => api.get<Record<string, string>>("/health/live", { auth: false }),
  ready: () => api.get<ReadinessReport>("/health/ready", { auth: false }),
};
