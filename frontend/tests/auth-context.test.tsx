/**
 * The session, end to end through the real client.
 *
 * `fetch` is the only thing replaced here — the provider, the API modules and
 * the token store are the shipped ones, because the bug this is guarding
 * against lives in how they fit together: a hard refresh has no access token,
 * only a cookie the JavaScript cannot see, and the provider has to turn that
 * into a signed-in user without treating a visitor's failed refresh as an
 * error.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/lib/auth/context";
import { resetClientState } from "@/lib/api/client";
import { getAccessToken, resetTokenStore } from "@/lib/auth/token-store";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/",
}));

const PROFILE = {
  id: "11111111-1111-4111-8111-111111111111",
  email: "nadia@university.edu",
  full_name: "Nadia Rahman",
  role: "student",
  gender: "female",
  total_xp: 1840,
  current_level: 9,
  current_streak_days: 6,
  longest_streak_days: 11,
  is_active: true,
  created_at: "2026-08-01T09:00:00+06:00",
};

const TOKENS = { access_token: "fresh", refresh_token: "r", expires_in: 1800 };

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function refused(code: string, message: string, status = 401): Response {
  return json({ error: { code, message, details: {} } }, status);
}

function Probe() {
  const { status, user, signIn, signOut } = useAuth();
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="user">{user?.full_name ?? "nobody"}</p>
      <button type="button" onClick={() => void signIn({ email: "a@b.edu", password: "pw" })}>
        Sign in
      </button>
      <button type="button" onClick={() => void signOut()}>
        Sign out
      </button>
    </div>
  );
}

function renderProvider() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetTokenStore();
  resetClientState();
  replace.mockClear();
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  resetTokenStore();
  resetClientState();
});

describe("bootstrapping a page load", () => {
  it("turns the refresh cookie into a signed-in user", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) return Promise.resolve(json(TOKENS));
      if (url.endsWith("/users/me")) return Promise.resolve(json(PROFILE));
      throw new Error(`unexpected request to ${url}`);
    });

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("user")).toHaveTextContent("Nadia Rahman");
    expect(getAccessToken()).toBe("fresh");
  });

  it("settles as anonymous for a visitor with no cookie, and does not redirect", async () => {
    fetchMock.mockResolvedValue(refused("INVALID_TOKEN", "No refresh token was supplied."));

    renderProvider();

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(screen.getByTestId("user")).toHaveTextContent("nobody");
    // The landing page is public. Bouncing anyone who has never signed in to
    // /login would make the front page unreachable.
    expect(replace).not.toHaveBeenCalled();
  });

  it("refreshes exactly once, however React re-renders", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) return Promise.resolve(json(TOKENS));
      return Promise.resolve(json(PROFILE));
    });

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    const refreshes = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/auth/refresh"));
    // The refresh token rotates on use, and presenting a rotated one is read
    // as theft — it revokes the whole session family.
    expect(refreshes).toHaveLength(1);
  });

  it("stays anonymous when the token is good but the profile cannot be read", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) return Promise.resolve(json(TOKENS));
      return Promise.resolve(refused("ACCOUNT_INACTIVE", "This account is not active."));
    });

    renderProvider();

    // A deactivated account holds a valid signature and no access. Half a
    // session — a token with no profile — is worse than none.
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(getAccessToken()).toBeNull();
  });
});

describe("signing in and out", () => {
  it("keeps the token and the profile from one login response", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) return Promise.resolve(refused("INVALID_TOKEN", "None."));
      if (url.endsWith("/auth/login")) {
        return Promise.resolve(json({ user: PROFILE, tokens: TOKENS }));
      }
      throw new Error(`unexpected request to ${url}`);
    });

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    // Login already returns the profile; asking /users/me for it again would
    // be a round trip for something in hand.
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/users/me"))).toHaveLength(
      0,
    );
    expect(getAccessToken()).toBe("fresh");
  });

  it("clears the session locally even when the server refuses the logout", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) return Promise.resolve(json(TOKENS));
      if (url.endsWith("/users/me")) return Promise.resolve(json(PROFILE));
      if (url.endsWith("/auth/logout"))
        return Promise.resolve(refused("INVALID_TOKEN", "Gone.", 401));
      throw new Error(`unexpected request to ${url}`);
    });

    renderProvider();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    // The server-side session may already have expired. Signing out is the
    // part the student asked for, and it has to happen either way.
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(getAccessToken()).toBeNull();
    expect(replace).toHaveBeenCalledWith("/login");
  });
});
