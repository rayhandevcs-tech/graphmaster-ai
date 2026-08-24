/**
 * The `next` parameter is attacker-controlled.
 *
 * A link to `/login?next=https://evil.example/` would put our own domain in
 * front of a student, take their password, and hand them to someone else's
 * page — the classic open redirect, and the reason this is a function with
 * tests rather than a condition inside a form handler.
 */

import { describe, expect, it } from "vitest";

import { safeNextPath } from "@/lib/auth/redirect";

const HOME = "/dashboard";

describe("safeNextPath", () => {
  it("keeps a path on this site", () => {
    expect(safeNextPath("/practice", HOME)).toBe("/practice");
  });

  it("keeps the query string with it", () => {
    expect(safeNextPath("/practice?graph=abc", HOME)).toBe("/practice?graph=abc");
  });

  it("falls back when there is no next at all", () => {
    expect(safeNextPath(null, HOME)).toBe(HOME);
    expect(safeNextPath("", HOME)).toBe(HOME);
  });

  it("refuses an absolute URL", () => {
    expect(safeNextPath("https://evil.example/", HOME)).toBe(HOME);
    expect(safeNextPath("http://evil.example/", HOME)).toBe(HOME);
  });

  it("refuses a protocol-relative URL", () => {
    // Starts with a slash, and is still another origin.
    expect(safeNextPath("//evil.example/", HOME)).toBe(HOME);
  });

  it("refuses a backslash-escaped one", () => {
    // Some browsers normalise `/\` to `//`.
    expect(safeNextPath("/\\evil.example", HOME)).toBe(HOME);
  });

  it("refuses a javascript: URL", () => {
    expect(safeNextPath("javascript:alert(1)", HOME)).toBe(HOME);
  });
});
