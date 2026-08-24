/**
 * The route guard.
 *
 * It decides what the interface shows, not what the API allows — every
 * endpoint checks the role server-side. What matters here is that it never
 * flashes a protected page before the session is known, and that a wrong role
 * is a dead end rather than a redirect the student cannot explain.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Protected, RoleGate } from "@/components/auth/protected";
import type { AuthContextValue } from "@/lib/auth/context";
import type { UserProfile, UserRole } from "@/types/api";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/dashboard",
}));

const authValue = vi.hoisted(() => ({ current: null as AuthContextValue | null }));

vi.mock("@/lib/auth/context", () => ({
  useAuth: () => authValue.current,
}));

function student(role: UserRole = "student"): UserProfile {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    email: "nadia@university.edu",
    full_name: "Nadia Rahman",
    role,
    gender: "female",
    total_xp: 1840,
    current_level: 9,
    current_streak_days: 6,
    longest_streak_days: 11,
    is_active: true,
    created_at: "2026-08-01T09:00:00+06:00",
  };
}

function signedIn(role: UserRole): AuthContextValue {
  return {
    user: student(role),
    status: "authenticated",
    isAuthenticated: true,
    signIn: vi.fn(),
    register: vi.fn(),
    signOut: vi.fn(),
    reloadUser: vi.fn(),
    applyUser: vi.fn(),
  } as unknown as AuthContextValue;
}

beforeEach(() => {
  replace.mockClear();
  window.history.replaceState({}, "", "/dashboard");
});

describe("<Protected>", () => {
  it("shows nothing of the page while the session is still unknown", () => {
    authValue.current = { ...signedIn("student"), status: "loading", user: null };

    render(
      <Protected>
        <p>Your streak is 6 days</p>
      </Protected>,
    );

    // A flash of a student's dashboard before the guard resolves is the
    // failure mode this prevents.
    expect(screen.queryByText("Your streak is 6 days")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Checking your session");
  });

  it("sends an anonymous visitor to the login page", async () => {
    authValue.current = { ...signedIn("student"), status: "anonymous", user: null };

    render(
      <Protected>
        <p>secret</p>
      </Protected>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalled());
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fdashboard");
  });

  it("remembers where they were going, query string and all", async () => {
    window.history.replaceState({}, "", "/practice?graph=abc");
    authValue.current = { ...signedIn("student"), status: "anonymous", user: null };

    render(
      <Protected>
        <p>secret</p>
      </Protected>,
    );

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/login?next=%2Fpractice%3Fgraph%3Dabc"),
    );
  });

  it("renders the page for a signed-in user when no role is demanded", () => {
    authValue.current = signedIn("student");

    render(
      <Protected>
        <p>Your streak is 6 days</p>
      </Protected>,
    );

    expect(screen.getByText("Your streak is 6 days")).toBeInTheDocument();
  });

  it("renders the page for a role that is allowed", () => {
    authValue.current = signedIn("teacher");

    render(
      <Protected roles={["teacher", "admin"]}>
        <p>Class overview</p>
      </Protected>,
    );

    expect(screen.getByText("Class overview")).toBeInTheDocument();
  });

  it("explains a wrong role instead of redirecting", () => {
    authValue.current = signedIn("student");

    render(
      <Protected roles={["teacher", "admin"]}>
        <p>Class overview</p>
      </Protected>,
    );

    expect(screen.queryByText("Class overview")).not.toBeInTheDocument();
    expect(screen.getByRole("heading")).toHaveTextContent("not for your account");
    // Bouncing them somewhere else would leave them wondering whether they
    // mistyped the address.
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/dashboard");
  });

  it("points a teacher at the teaching home, not the student one", () => {
    authValue.current = signedIn("teacher");

    render(
      <Protected roles={["student"]}>
        <p>Practice</p>
      </Protected>,
    );

    expect(screen.getByRole("link")).toHaveAttribute("href", "/teacher/dashboard");
  });
});

describe("<RoleGate>", () => {
  it("shows a control to the role that may use it", () => {
    authValue.current = signedIn("admin");

    render(
      <RoleGate roles={["admin"]}>
        <button type="button">Adjust XP</button>
      </RoleGate>,
    );

    expect(screen.getByRole("button", { name: "Adjust XP" })).toBeInTheDocument();
  });

  it("hides it from everyone else rather than letting them be refused", () => {
    authValue.current = signedIn("student");

    render(
      <RoleGate roles={["admin"]} fallback={<span>nothing here</span>}>
        <button type="button">Adjust XP</button>
      </RoleGate>,
    );

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("nothing here")).toBeInTheDocument();
  });
});
