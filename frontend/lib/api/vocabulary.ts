import { api, type PageParams } from "./client";
import type {
  PageVocabularyItemOut,
  UUID,
  VocabularyBulkCreateRequest,
  VocabularyBulkResult,
  VocabularyCategoryOut,
  VocabularyItemCreate,
  VocabularyItemOut,
  VocabularyItemUpdate,
} from "@/types/api";

export interface VocabularyListParams extends PageParams {
  category?: string;
  is_active?: boolean;
  search?: string;
}

export const vocabularyApi = {
  categories: () => api.get<VocabularyCategoryOut[]>("/vocabulary/categories"),

  list: (params: VocabularyListParams = {}) =>
    api.get<PageVocabularyItemOut>("/vocabulary/items", { query: { ...params } }),

  get: (itemId: UUID) => api.get<VocabularyItemOut>(`/vocabulary/items/${itemId}`),

  /** `is_phrase` is derived from the term by the server and must not be sent. */
  create: (payload: VocabularyItemCreate) =>
    api.post<VocabularyItemOut>("/vocabulary/items", payload),

  createMany: (payload: VocabularyBulkCreateRequest) =>
    api.post<VocabularyBulkResult>("/vocabulary/items/bulk", payload),

  update: (itemId: UUID, payload: VocabularyItemUpdate) =>
    api.patch<VocabularyItemOut>(`/vocabulary/items/${itemId}`, payload),

  /**
   * A soft delete — it returns the deactivated item rather than nothing,
   * because historical scores still reference it and the row survives.
   */
  deactivate: (itemId: UUID) => api.delete<VocabularyItemOut>(`/vocabulary/items/${itemId}`),
};
