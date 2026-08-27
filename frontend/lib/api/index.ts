/**
 * The API surface, one module per resource.
 *
 * Import from here (`import { graphsApi } from "@/lib/api"`) so a component
 * never reaches for `fetch` and the contract has one representation in the
 * codebase (06-frontend-architecture §6).
 */

export { api, API_BASE_URL, download, request, setUnauthenticatedHandler } from "./client";
export type { DownloadedFile, PageParams, RequestOptions } from "./client";
export { ApiError, NetworkError, errorMessage } from "./errors";
export type { ErrorEnvelope } from "./errors";

export { analysisApi } from "./analysis";
export { analyticsApi } from "./analytics";
export { assessmentApi } from "./assessment";
export type { AssessmentScope } from "./assessment";
export { assignmentsApi } from "./assignments";
export type { AssignmentListParams } from "./assignments";
export { authApi } from "./auth";
export { avatarsApi } from "./avatars";
export { classesApi } from "./classes";
export { gamificationApi } from "./gamification";
export { graphsApi, isAuthoringDetail } from "./graphs";
export type { Graph } from "./graphs";
export { healthApi } from "./health";
export { leaderboardApi } from "./leaderboard";
export { ocrApi } from "./ocr";
export { reportsApi } from "./reports";
export { submissionsApi } from "./submissions";
export { usersApi } from "./users";
export { vocabularyApi } from "./vocabulary";

export { queryKeys, INVALIDATED_BY_SCORING } from "./query-keys";
