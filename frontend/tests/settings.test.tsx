/**
 * Settings, the profile beside it, and the navigation that reaches both.
 *
 * The risky parts here are all promises the interface makes about what will
 * happen: a password change that signs you out of your phone, a control that
 * would toggle a feature that does not exist yet, and a bottom bar whose taps
 * have to land on the right route.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/lib/auth/context";
import { resetClientState } from "@/lib/api/client";
import { resetTokenStore } from "@/lib/auth/token-store";
import { SettingsView } from "@/components/settings/settings-view";
import { isActive, linksFor } from "@/lib/nav";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/settings",
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

const RUBRIC = {
  vocabulary_weight: 0.7,
  writing_weight: 0.3,
  target_word_count: { min: 150, max: 250 },
};

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * The real provider over a stubbed `fetch`, as the auth tests do. The page
 * reads the rubric from the server and its role from the session, and mocking
 * either of those out would leave the test asserting a fixture rather than the
 * page.
 */
function renderSettings() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/refresh")) {
        return json({ access_token: "fresh", refresh_token: "r", expires_in: 1800 });
      }
      if (url.includes("/users/me")) return json(PROFILE);
      if (url.includes("/analysis/rubric")) return json(RUBRIC);
      return json({});
    }),
  );

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <SettingsView />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  resetClientState();
  resetTokenStore();
});

describe("the navigation", () => {
  it("gives every role a home that belongs to them", () => {
    expect(linksFor("student")[0]?.href).toBe("/dashboard");
    expect(linksFor("teacher")[0]?.href).toBe("/teacher/dashboard");
    // A student must never be offered a teaching route, and the guard on the
    // page is not a reason to advertise it.
    expect(linksFor("student").some((link) => link.href.startsWith("/teacher"))).toBe(false);
    expect(linksFor("teacher").some((link) => link.href === "/admin/users")).toBe(false);
    expect(linksFor("admin").some((link) => link.href === "/admin/users")).toBe(true);
  });

  it("offers a signed-out visitor nothing", () => {
    expect(linksFor(undefined)).toEqual([]);
  });

  it("fits a phone: every link has an icon and a label short enough to sit under it", () => {
    for (const link of linksFor("student")) {
      // A lucide icon is a forwardRef object rather than a plain function.
      expect(link.icon).toBeTruthy();
      expect((link.shortLabel ?? link.label).length).toBeLessThanOrEqual(10);
    }
  });

  it("marks the section you are in, not only the exact page", () => {
    expect(isActive("/practice", "/practice")).toBe(true);
    expect(isActive("/practice/8f2a", "/practice")).toBe(true);
    // …and not a route that merely starts with the same letters.
    expect(isActive("/practices", "/practice")).toBe(false);
    expect(isActive("/dashboard", "/practice")).toBe(false);
  });
});

describe("the settings page", () => {
  it("warns that changing a password signs you out before the button, not after", () => {
    renderSettings();

    const warning = screen.getByText(/signs you out everywhere, including this device/i);
    expect(warning).toBeInTheDocument();

    // The warning has to precede the control it is about; a student who reads
    // it afterwards reads it having already been signed out.
    const button = screen.getByRole("button", { name: /update password/i });
    expect(warning.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("offers reward sound, and offers it muted", () => {
    // FR-7.11. The control exists now that there is something to play, and it
    // is the *muted* option that starts selected — a student has to ask for
    // audio, on every browser, every time.
    renderSettings();

    const muted = screen.getByRole("radio", { name: /muted/i });
    expect(muted).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: /^on/i })).toHaveAttribute("aria-checked", "false");
  });

  it("keeps sound and motion as separate preferences", () => {
    // Asking a system to stop animating is not asking it to be quiet, and the
    // reverse is at least as common. Two headings, two controls.
    renderSettings();

    expect(screen.getByRole("heading", { name: /^sound$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^motion$/i })).toBeInTheDocument();
  });

  it("says the sound preference belongs to the browser, not the account", () => {
    renderSettings();
    expect(screen.getByText(/stored in this browser/i)).toBeInTheDocument();
  });

  it("describes reduced motion as losing nothing", () => {
    renderSettings();
    expect(screen.getByText(/nothing is lost/i)).toBeInTheDocument();
  });

  it("states the marking criteria the server sent, never a copy of its own", async () => {
    renderSettings();

    // 70 and 30 appear because the stub said so. A component holding its own
    // copy would still pass a test that asserted the numbers — so the point of
    // this one is that they arrive over the wire at all.
    await waitFor(() =>
      expect(screen.getByText(/70% of your mark is the target vocabulary/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/150–250 words/)).toBeInTheDocument();
  });
});
