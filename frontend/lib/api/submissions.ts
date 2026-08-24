import { api, type DownloadedFile, type PageParams } from "./client";
import type {
  ExtractionResult,
  PageSubmissionSummary,
  RewardTier,
  SubmissionCreate,
  SubmissionDetail,
  SubmissionResult,
  SubmissionStatus,
  SubmissionTextUpdate,
  UUID,
} from "@/types/api";

export interface SubmissionListParams extends PageParams {
  graph_id?: UUID;
  /** Teachers and admins only. A student's list is their own, always. */
  student_id?: UUID;
  class_id?: UUID;
  status?: SubmissionStatus;
  reward_tier?: RewardTier;
  scored_only?: boolean;
}

export const submissionsApi = {
  /** Opens an attempt. `input_method` is fixed here and never flips afterwards. */
  create: (payload: SubmissionCreate) => api.post<SubmissionDetail>("/submissions", payload),

  get: (submissionId: UUID) => api.get<SubmissionDetail>(`/submissions/${submissionId}`),

  list: (params: SubmissionListParams = {}) =>
    api.get<PageSubmissionSummary>("/submissions", { query: { ...params } }),

  /**
   * Uploads the handwriting and runs recognition.
   *
   * A 422 (`OCR_FAILED`) leaves the submission in `failed` with the image
   * kept, so the student can retry or type instead without re-photographing
   * the page. A 503 means the server has no recognition engine at all, and
   * consumes nothing.
   */
  upload: (submissionId: UUID, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<ExtractionResult>(`/submissions/${submissionId}/upload`, form);
  },

  /** Sets or corrects the answer before analysis — this is FR-4.7's editable preview. */
  setText: (submissionId: UUID, payload: SubmissionTextUpdate) =>
    api.patch<SubmissionDetail>(`/submissions/${submissionId}/text`, payload),

  /**
   * Scores the attempt and awards XP, achievements and the tier badge.
   *
   * Exactly once: a second call on a scored submission is a 409, and a new
   * attempt at the same graph is a new submission rather than a rescore.
   */
  analyze: (submissionId: UUID) =>
    api.post<SubmissionResult>(`/submissions/${submissionId}/analyze`),

  /** Discards an unscored draft. A scored submission is frozen and cannot be deleted. */
  remove: (submissionId: UUID) => api.delete<void>(`/submissions/${submissionId}`),

  /**
   * The original handwriting image.
   *
   * Streamed through an authenticated endpoint, never a static URL, so the
   * storage key never leaves the server. The caller gets a blob and makes an
   * object URL — a bearer token cannot ride on an `<img src>`.
   */
  image: (submissionId: UUID): Promise<DownloadedFile> =>
    api.download(`/submissions/${submissionId}/image`, {}, "handwriting"),
};
