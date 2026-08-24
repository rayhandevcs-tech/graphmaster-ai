/**
 * The error envelope, as one type.
 *
 * Every failure the API can produce arrives in the shape described in
 * 04-api-design.md §5.2 — domain errors, validation failures, 404s from
 * Starlette and unhandled 500s alike, because the backend reshapes all of them
 * through one set of handlers. That is what makes a single class here honest
 * rather than optimistic.
 */

/** `{"error": {"code": ..., "message": ..., "details": {...}}}` */
export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const inner = (value as { error: unknown }).error;
  return (
    typeof inner === "object" &&
    inner !== null &&
    typeof (inner as { code?: unknown }).code === "string" &&
    typeof (inner as { message?: unknown }).message === "string"
  );
}

/**
 * A request the server answered, and refused.
 *
 * `message` is the server's own wording. It is written for a student to read —
 * "Submission not found, or you do not have access to it." — so components
 * show it rather than substituting a generic line, which would lose the
 * distinction between the several things a 409 can mean.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  /** From `Retry-After` on a 429, in seconds. */
  readonly retryAfterSeconds: number | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
    retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryAfterSeconds = retryAfterSeconds;
  }

  /** Missing, invalid or expired credentials. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  /** Authenticated, but the role is wrong. Distinct from 401 on purpose. */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }

  /**
   * A deployment fault rather than anything the student did: no language
   * model, no recognition engine, no Excel library. Worth its own check
   * because the interface should say "this server cannot do that yet" instead
   * of blaming the answer.
   */
  get isServiceUnavailable(): boolean {
    return this.status === 503;
  }

  /**
   * Per-field messages from a 422, keyed by the field path the server used
   * (`details.fields`). Empty for every other status, so a form can call this
   * unconditionally.
   */
  get fieldErrors(): Record<string, string> {
    const fields = this.details.fields;
    if (typeof fields !== "object" || fields === null) return {};
    return Object.fromEntries(
      Object.entries(fields as Record<string, unknown>).map(([key, value]) => [key, String(value)]),
    );
  }
}

/**
 * The request never reached a server, or the reply was unreadable.
 *
 * Kept separate from `ApiError` because the two need opposite advice: a
 * network failure is worth retrying, a refused request is not.
 */
export class NetworkError extends Error {
  override readonly cause?: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "NetworkError";
    this.cause = cause;
  }
}

/** Anything a component can show the user, whatever went wrong. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof NetworkError) return "Could not reach the server. Check your connection.";
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong.";
}
