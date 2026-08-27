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
import { roleCanVisit } from "@/lib/auth/roles";

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

describe("where a role may actually be sent", () => {
  it("keeps a student out of the teacher and admin screens", () => {
    expect(roleCanVisit("/teacher/dashboard", "student")).toBe(false);
    expect(roleCanVisit("/teacher/submissions/abc", "student")).toBe(false);
    expect(roleCanVisit("/admin/users", "student")).toBe(false);
  });

  it("keeps a teacher out of the admin screens and the student practice loop", () => {
    expect(roleCanVisit("/admin/users", "teacher")).toBe(false);
    expect(roleCanVisit("/dashboard", "teacher")).toBe(false);
    expect(roleCanVisit("/practice", "teacher")).toBe(false);
  });

  it("lets each role reach its own pages", () => {
    expect(roleCanVisit("/dashboard", "student")).toBe(true);
    expect(roleCanVisit("/practice/some-graph-id", "student")).toBe(true);
    expect(roleCanVisit("/teacher/analytics", "teacher")).toBe(true);
    expect(roleCanVisit("/teacher/analytics", "admin")).toBe(true);
    expect(roleCanVisit("/admin/users", "admin")).toBe(true);
  });

  it("lets every signed-in role reach the shared pages", () => {
    for (const role of ["student", "teacher", "admin"] as const) {
      expect(roleCanVisit("/profile", role)).toBe(true);
      expect(roleCanVisit("/settings", role)).toBe(true);
    }
  });

  it("is not defeated by a query string or a fragment", () => {
    // `/teacher/submissions?student=x` is the same page as
    // `/teacher/submissions`, and a prefix match on the raw string would miss
    // it if the query were left attached.
    expect(roleCanVisit("/teacher/submissions?student=abc", "student")).toBe(false);
    expect(roleCanVisit("/teacher/dashboard#top", "student")).toBe(false);
  });

  it("refuses everything when there is no role yet", () => {
    expect(roleCanVisit("/dashboard", undefined)).toBe(false);
  });

  it("does not mistake a longer name for the prefix", () => {
    // `/dashboards-of-doom` is not `/dashboard`.
    expect(roleCanVisit("/practice-notes", "teacher")).toBe(true);
  });
});
