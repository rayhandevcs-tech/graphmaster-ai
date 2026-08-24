/**
 * The fetch wrapper.
 *
 * Everything the app knows about the network is decided here: which requests
 * carry a token, what happens to the one that comes back 401, and how a
 * refused request becomes something a component can show. Each of those has a
 * failure mode that is invisible until it is not — a refresh storm that
 * revokes a student's session mid-dashboard, or an error whose message is
 * "[object Object]".
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, NetworkError } from "@/lib/api/errors";
import { api, request, resetClientState, setUnauthenticatedHandler } from "@/lib/api/client";
import { getAccessToken, resetTokenStore, setAccessToken } from "@/lib/auth/token-store";

const BASE = "http://localhost:8000/api/v1";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function envelope(code: string, message: string, details: Record<string, unknown> = {}) {
  return { error: { code, message, details } };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetTokenStore();
  resetClientState();
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  resetTokenStore();
  resetClientState();
});

describe("building the request", () => {
  it("prefixes the base URL and returns the parsed body", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));

    const body = await request<{ status: string }>("/health/live", { auth: false });

    expect(body).toEqual({ status: "ok" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`${BASE}/health/live`);
  });

  it("drops empty query parameters rather than sending them blank", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ items: [] }));

    await api.get("/graphs", {
      query: { search: "", difficulty: undefined, graph_type: null, page: 2 },
    });

    // An empty `search=` is not the same request as no search at all: one
    // filters on the empty string, the other does not filter.
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.get("search")).toBeNull();
    expect(url.searchParams.get("difficulty")).toBeNull();
    expect(url.searchParams.get("graph_type")).toBeNull();
    expect(url.searchParams.get("page")).toBe("2");
  });

  it("repeats an array parameter instead of joining it", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}));

    await api.get("/submissions", { query: { status: ["draft", "scored"] } });

    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.getAll("status")).toEqual(["draft", "scored"]);
  });

  it("sends the bearer token when there is one", async () => {
    setAccessToken("token-abc");
    fetchMock.mockResolvedValueOnce(jsonResponse({}));

    await api.get("/users/me");

    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer token-abc");
  });

  it("omits the token from the endpoints that mint one", async () => {
    setAccessToken("token-abc");
    fetchMock.mockResolvedValueOnce(jsonResponse({}));

    await api.post("/auth/login", { email: "a@b.edu", password: "x" }, { auth: false });

    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("always sends credentials, because the refresh token is a cookie", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}));

    await api.get("/users/me");

    expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe("include");
  });

  it("leaves multipart bodies alone so the browser can set the boundary", async () => {
    const form = new FormData();
    form.append("file", new File(["x"], "answer.png", { type: "image/png" }));
    fetchMock.mockResolvedValueOnce(jsonResponse({}));

    await api.post("/ocr/extract", form);

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    // A hand-written multipart Content-Type has no boundary, and the server
    // cannot parse the body without one.
    expect(headers["Content-Type"]).toBeUndefined();
    expect(init.body).toBe(form);
  });

  it("serialises anything else as JSON", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}));

    await api.patch("/users/me", { full_name: "Nadia Rahman" });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ full_name: "Nadia Rahman" }));
  });
});

describe("reading the reply", () => {
  it("turns the error envelope into an ApiError", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        envelope("SUBMISSION_NOT_FOUND", "Submission not found, or you do not have access to it."),
        {
          status: 404,
        },
      ),
    );

    const error = await api.get("/submissions/x").catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(404);
    expect(apiError.code).toBe("SUBMISSION_NOT_FOUND");
    // The server's wording, not a substitute: it distinguishes "not yours"
    // from "gone", which a generic "Not found" would lose.
    expect(apiError.message).toContain("do not have access");
    expect(apiError.isNotFound).toBe(true);
  });

  it("exposes a 422's per-field messages for a form to place", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        envelope("VALIDATION_ERROR", "The request could not be processed.", {
          fields: { email: "value is not a valid email address", password: "too short" },
        }),
        { status: 422 },
      ),
    );

    const error = (await api
      .post("/auth/register", {}, { auth: false })
      .catch((e) => e)) as ApiError;

    expect(error.fieldErrors).toEqual({
      email: "value is not a valid email address",
      password: "too short",
    });
  });

  it("has no field errors for a status that carries none", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(envelope("INVALID_CREDENTIALS", "Email or password is incorrect."), {
        status: 401,
      }),
    );

    const error = (await api.post("/auth/login", {}, { auth: false }).catch((e) => e)) as ApiError;

    // Callable unconditionally, so a form does not have to check the status
    // before asking.
    expect(error.fieldErrors).toEqual({});
  });

  it("keeps the status when the body is not the envelope", async () => {
    // A proxy's HTML 502 — real, and unparseable.
    fetchMock.mockResolvedValueOnce(
      new Response("<html>Bad Gateway</html>", { status: 502, statusText: "Bad Gateway" }),
    );

    const error = (await api.get("/graphs").catch((e) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(502);
    expect(error.code).toBe("HTTP_502");
  });

  it("reads Retry-After from a 429", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(envelope("RATE_LIMITED", "Too many attempts. Try again shortly."), {
        status: 429,
        headers: { "Content-Type": "application/json", "Retry-After": "42" },
      }),
    );

    const error = (await api.post("/auth/login", {}, { auth: false }).catch((e) => e)) as ApiError;

    expect(error.isRateLimited).toBe(true);
    expect(error.retryAfterSeconds).toBe(42);
  });

  it("returns undefined for a 204 rather than failing to parse nothing", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(api.delete("/submissions/x")).resolves.toBeUndefined();
  });

  it("reports an unreachable server as a NetworkError, not an ApiError", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const error = await api.get("/users/me").catch((caught: unknown) => caught);

    // The two need opposite advice: retry this one, do not retry a refusal.
    expect(error).toBeInstanceOf(NetworkError);
  });

  it("propagates an abort rather than dressing it as a network failure", async () => {
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(new DOMException("Aborted", "AbortError"));

    const error = await api
      .get("/users/me", { signal: controller.signal })
      .catch((caught: unknown) => caught);

    expect(error).not.toBeInstanceOf(NetworkError);
    expect((error as DOMException).name).toBe("AbortError");
  });
});

describe("the 401 retry", () => {
  it("refreshes once and replays the request", async () => {
    setAccessToken("expired");

    fetchMock
      .mockResolvedValueOnce(jsonResponse(envelope("TOKEN_EXPIRED", "Expired."), { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "fresh", refresh_token: "r", expires_in: 1800 }),
      )
      .mockResolvedValueOnce(jsonResponse({ id: "u1" }));

    const profile = await api.get<{ id: string }>("/users/me");

    expect(profile).toEqual({ id: "u1" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe(`${BASE}/auth/refresh`);
    // The replay carries the new token, not the one the server just refused.
    const replayHeaders = fetchMock.mock.calls[2]?.[1]?.headers as Record<string, string>;
    expect(replayHeaders.Authorization).toBe("Bearer fresh");
    expect(getAccessToken()).toBe("fresh");
  });

  it("gives up after one retry instead of looping", async () => {
    setAccessToken("expired");

    fetchMock
      .mockResolvedValueOnce(jsonResponse(envelope("TOKEN_EXPIRED", "Expired."), { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: "fresh", refresh_token: "r", expires_in: 1800 }),
      )
      .mockResolvedValueOnce(jsonResponse(envelope("TOKEN_EXPIRED", "Expired."), { status: 401 }));

    await expect(api.get("/users/me")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("refreshes once for a burst of concurrent 401s", async () => {
    setAccessToken("expired");

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        return Promise.resolve(
          jsonResponse({ access_token: "fresh", refresh_token: "r", expires_in: 1800 }),
        );
      }
      const headers = (init?.headers ?? {}) as Record<string, string>;
      if (headers.Authorization === "Bearer fresh")
        return Promise.resolve(jsonResponse({ ok: true }));
      return Promise.resolve(jsonResponse(envelope("TOKEN_EXPIRED", "Expired."), { status: 401 }));
    });

    await Promise.all([api.get("/users/me"), api.get("/graphs"), api.get("/submissions")]);

    const refreshes = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/auth/refresh"));
    // Three refreshes would rotate the token three times, and the backend
    // treats a reused rotated token as theft — revoking the whole family and
    // signing the student out for loading a page.
    expect(refreshes).toHaveLength(1);
  });

  it("does not refresh for a request that was not authenticated", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(envelope("INVALID_CREDENTIALS", "Email or password is incorrect."), {
        status: 401,
      }),
    );

    await expect(api.post("/auth/login", {}, { auth: false })).rejects.toBeInstanceOf(ApiError);

    // A failed login is the answer, not a stale credential.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("signs out a session that existed when the refresh is refused", async () => {
    setAccessToken("expired");
    const onUnauthenticated = vi.fn();
    setUnauthenticatedHandler(onUnauthenticated);

    fetchMock
      .mockResolvedValueOnce(jsonResponse(envelope("TOKEN_EXPIRED", "Expired."), { status: 401 }))
      .mockResolvedValueOnce(
        jsonResponse(envelope("INVALID_TOKEN", "No refresh token."), { status: 401 }),
      );

    await expect(api.get("/users/me")).rejects.toBeInstanceOf(ApiError);

    expect(onUnauthenticated).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });

  it("does not sign out a visitor who was never signed in", async () => {
    const onUnauthenticated = vi.fn();
    setUnauthenticatedHandler(onUnauthenticated);

    fetchMock
      .mockResolvedValueOnce(
        jsonResponse(envelope("UNAUTHORIZED", "Authentication required."), { status: 401 }),
      )
      .mockResolvedValueOnce(
        jsonResponse(envelope("INVALID_TOKEN", "No refresh token."), { status: 401 }),
      );

    await expect(api.get("/users/me")).rejects.toBeInstanceOf(ApiError);

    // Otherwise the landing page's bootstrap refresh — which is expected to
    // fail for anyone who has never signed in — bounces every visitor to
    // /login.
    expect(onUnauthenticated).not.toHaveBeenCalled();
  });

  it("keeps the token when the refresh fails for want of a network", async () => {
    setAccessToken("still-good");
    const onUnauthenticated = vi.fn();
    setUnauthenticatedHandler(onUnauthenticated);

    fetchMock
      .mockResolvedValueOnce(jsonResponse(envelope("TOKEN_EXPIRED", "Expired."), { status: 401 }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(api.get("/users/me")).rejects.toBeInstanceOf(ApiError);

    // A dropped connection is not a revoked session; discarding the token
    // here would sign a student out for walking into a lift.
    expect(onUnauthenticated).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("still-good");
  });
});

describe("downloads", () => {
  it("takes the filename from Content-Disposition", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("id,score\n", {
        status: 200,
        headers: {
          "Content-Type": "text/csv",
          "Content-Disposition": 'attachment; filename="class-report-2026-08.csv"',
        },
      }),
    );

    const file = await api.download("/reports/r1/download", {}, "report");

    expect(file.filename).toBe("class-report-2026-08.csv");
    expect(file.contentType).toBe("text/csv");
    expect(await file.blob.text()).toBe("id,score\n");
  });

  it("falls back to the caller's name when the header says nothing", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("x", {
        status: 200,
        headers: { "Content-Type": "image/png" },
      }),
    );

    const file = await api.download("/submissions/s1/image", {}, "handwriting");

    expect(file.filename).toBe("handwriting");
  });

  it("raises the error envelope from a failed download", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(envelope("REPORT_NOT_READY", "This report is still being generated."), {
        status: 409,
      }),
    );

    const error = (await api.download("/reports/r1/download").catch((e) => e)) as ApiError;

    expect(error.code).toBe("REPORT_NOT_READY");
  });
});
