import { api, type DownloadedFile, type PageParams } from "./client";
import type {
  PageReportOut,
  ReportCapabilities,
  ReportOut,
  ReportRequest,
  UUID,
} from "@/types/api";

export const reportsApi = {
  /**
   * Which formats this deployment can actually produce.
   *
   * CSV is always available; Excel and PDF depend on optional libraries. Read
   * this to disable the formats the server cannot build, rather than offering
   * all three and answering a click with a 503.
   */
  capabilities: () => api.get<ReportCapabilities>("/reports/capabilities"),

  create: (payload: ReportRequest) => api.post<ReportOut>("/reports", payload),

  list: (params: PageParams = {}) => api.get<PageReportOut>("/reports", { query: { ...params } }),

  get: (reportId: UUID) => api.get<ReportOut>(`/reports/${reportId}`),

  /** The generated file. `filename` comes from the server's `Content-Disposition`. */
  download: (reportId: UUID): Promise<DownloadedFile> =>
    api.download(`/reports/${reportId}/download`, {}, "report"),

  remove: (reportId: UUID) => api.delete<void>(`/reports/${reportId}`),
};
