/**
 * The one place the frontend talks to the network.
 *
 * Components never call `fetch` (06-frontend-architecture §6). Everything goes
 * through here, so the base URL, the bearer header, the error envelope and the
 * refresh dance each exist once. The resource modules beside this file are thin
 * typed wrappers over `api.get` and friends; if you find yourself adding a
 * second copy of any of this, the resource module is the wrong place for it.
 */

import { ApiError, NetworkError, isErrorEnvelope } from "./errors";
import { getAccessToken, setAccessToken } from "@/lib/auth/token-store";
import type { TokenPair } from "@/types/api";

/**
 * Read statically so Next can inline it at build time — `process.env` is not
 * an object in the browser bundle, and a computed lookup would be `undefined`.
 */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export type QueryValue =
  string | number | boolean | readonly (string | number)[] | null | undefined;

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** Sent as JSON, unless it is a `FormData`, which is passed through. */
  body?: unknown;
  /** `null` and `undefined` entries are dropped rather than sent empty. */
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
  /**
   * Attach the bearer token and refresh once on a 401. Off for the endpoints
   * that mint credentials — a failed login is the answer, not a hint to go
   * and fetch a token.
   */
  auth?: boolean;
  headers?: Record<string, string>;
}

/* -------------------------------------------------------------------------- */
/* Refresh                                                                     */
/* -------------------------------------------------------------------------- */

let refreshInFlight: Promise<string | null> | null = null;
let unauthenticatedHandler: (() => void) | null = null;

/**
 * Called when a refresh fails for someone who *had* a session — i.e. it
 * expired or was revoked. `AuthProvider` registers a handler that clears the
 * user and sends them to the login page.
 */
export function setUnauthenticatedHandler(handler: (() => void) | null): void {
  unauthenticatedHandler = handler;
}

async function performRefresh(): Promise<string | null> {
  // Whether this can succeed at all depends on a cookie this code cannot read,
  // so the only way to find out is to ask.
  const hadToken = getAccessToken() !== null;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    });

    if (response.ok) {
      const tokens = (await response.json()) as TokenPair;
      setAccessToken(tokens.access_token);
      return tokens.access_token;
    }
  } catch {
    // A network failure is not a signed-out user. Fall through: the caller
    // reports the original error, and the next attempt can still succeed.
    return null;
  }

  setAccessToken(null);

  // Only a session that existed can end. Without this check the landing page's
  // bootstrap refresh — which is *expected* to fail for a visitor who has
  // never signed in — would bounce every anonymous visitor to /login.
  if (hadToken) unauthenticatedHandler?.();

  return null;
}

/**
 * One refresh at a time.
 *
 * A dashboard fires several requests at once; if the token expired they all
 * return 401 together. Without this they would each rotate the refresh token,
 * and the backend treats a second use of a rotated token as theft — revoking
 * the whole session family and signing the student out for loading a page.
 */
function refreshAccessToken(): Promise<string | null> {
  refreshInFlight ??= performRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

/* -------------------------------------------------------------------------- */
/* Requests                                                                    */
/* -------------------------------------------------------------------------- */

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = new URL(`${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) url.searchParams.append(key, String(item));
    } else {
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

function buildInit(options: RequestOptions, token: string | null): RequestInit {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;

  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (isFormData) {
    // Never set Content-Type for multipart: the browser has to add the
    // boundary, and a hand-written header omits it.
    body = options.body as FormData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  return {
    method: options.method ?? "GET",
    headers,
    body,
    signal: options.signal,
    // Carries the HttpOnly refresh cookie. Requires the API's
    // `allow_credentials`, which it sets for exactly this reason.
    credentials: "include",
  };
}

async function toApiError(response: Response): Promise<ApiError> {
  const retryAfter = response.headers.get("Retry-After");
  let code = `HTTP_${response.status}`;
  let message = response.statusText || "The request failed.";
  let details: Record<string, unknown> = {};

  try {
    const payload: unknown = await response.json();
    if (isErrorEnvelope(payload)) {
      code = payload.error.code;
      message = payload.error.message;
      details = payload.error.details ?? {};
    }
  } catch {
    // A body that is not JSON — a proxy's HTML 502, say. The status still
    // carries the meaning, so the request fails with what is known rather
    // than with a parse error nobody can act on.
  }

  return new ApiError(
    response.status,
    code,
    message,
    details,
    retryAfter === null ? null : Number(retryAfter),
  );
}

/**
 * Send once, refresh and send again on a 401, then give up.
 *
 * Exactly one retry: a token the server refuses twice will be refused a third
 * time, and a loop here would hammer the API on every expired session.
 */
async function send(path: string, options: RequestOptions): Promise<Response> {
  const useAuth = options.auth !== false;
  const url = buildUrl(path, options.query);

  let response: Response;
  try {
    response = await fetch(url, buildInit(options, useAuth ? getAccessToken() : null));
  } catch (cause) {
    if (options.signal?.aborted) throw cause;
    throw new NetworkError(`Could not reach ${url}`, cause);
  }

  if (response.status !== 401 || !useAuth) return response;

  const refreshed = await refreshAccessToken();
  if (refreshed === null) return response;

  try {
    return await fetch(url, buildInit(options, refreshed));
  } catch (cause) {
    if (options.signal?.aborted) throw cause;
    throw new NetworkError(`Could not reach ${url}`, cause);
  }
}

/** A JSON request. `T` is the response model from `types/api.ts`. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options);

  if (!response.ok) throw await toApiError(response);

  // 204, and the 200s whose body is genuinely empty.
  if (response.status === 204 || response.headers.get("Content-Length") === "0") {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch (cause) {
    throw new NetworkError("The server's reply could not be read as JSON.", cause);
  }
}

export interface DownloadedFile {
  blob: Blob;
  /** From `Content-Disposition`, falling back to the caller's suggestion. */
  filename: string;
  contentType: string;
}

/**
 * A binary response: a report export, or a student's handwriting image.
 *
 * These endpoints demand a bearer token, so the browser cannot fetch them with
 * an `<img src>` or a plain link — the file comes back as a blob and the caller
 * makes an object URL out of it.
 */
export async function download(
  path: string,
  options: RequestOptions = {},
  fallbackFilename = "download",
): Promise<DownloadedFile> {
  const response = await send(path, options);
  if (!response.ok) throw await toApiError(response);

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);

  return {
    blob: await response.blob(),
    filename: match?.[1] ? decodeURIComponent(match[1]) : fallbackFilename,
    contentType: response.headers.get("Content-Type") ?? "application/octet-stream",
  };
}

export const api = {
  get: <T>(path: string, options: Omit<RequestOptions, "method" | "body"> = {}) =>
    request<T>(path, { ...options, method: "GET" }),

  post: <T>(path: string, body?: unknown, options: Omit<RequestOptions, "method"> = {}) =>
    request<T>(path, { ...options, method: "POST", body }),

  patch: <T>(path: string, body?: unknown, options: Omit<RequestOptions, "method"> = {}) =>
    request<T>(path, { ...options, method: "PATCH", body }),

  put: <T>(path: string, body?: unknown, options: Omit<RequestOptions, "method"> = {}) =>
    request<T>(path, { ...options, method: "PUT", body }),

  delete: <T>(path: string, options: Omit<RequestOptions, "method" | "body"> = {}) =>
    request<T>(path, { ...options, method: "DELETE" }),

  download,
};

/** Test seam: drops any refresh that a previous test left in flight. */
export function resetClientState(): void {
  refreshInFlight = null;
  unauthenticatedHandler = null;
}

/** Every list endpoint takes these; `page` is 1-indexed and `page_size` caps at 100. */
export interface PageParams {
  page?: number;
  page_size?: number;
}
