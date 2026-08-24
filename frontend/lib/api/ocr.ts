import { api } from "./client";
import type { OCRExtractionResponse, OCRStatusResponse } from "@/types/api";

export const ocrApi = {
  /**
   * Which engines this deployment can actually use.
   *
   * Read before offering handwriting at all: on a server with no engine
   * configured the option should be hidden, rather than letting a student
   * photograph a page and only then be told it cannot be read.
   */
  status: () => api.get<OCRStatusResponse>("/ocr/status"),

  /** Recognition without a submission — the standalone preview surface. */
  extract: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<OCRExtractionResponse>("/ocr/extract", form);
  },
};
