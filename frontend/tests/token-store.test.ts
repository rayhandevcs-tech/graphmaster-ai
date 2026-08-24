/**
 * Where the access token lives.
 *
 * The interesting assertion is the one that fails on the server: module state
 * in a Node process is shared by every request it handles, so a token written
 * there would be handed to the next student to load a page.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getAccessToken,
  resetTokenStore,
  setAccessToken,
  subscribeToAccessToken,
} from "@/lib/auth/token-store";

afterEach(() => resetTokenStore());

describe("the token store", () => {
  it("starts empty, which is what a hard refresh looks like", () => {
    expect(getAccessToken()).toBeNull();
  });

  it("holds a token and gives it back", () => {
    setAccessToken("abc");
    expect(getAccessToken()).toBe("abc");
  });

  it("tells subscribers when the token changes", () => {
    const listener = vi.fn();
    subscribeToAccessToken(listener);

    setAccessToken("abc");
    setAccessToken(null);

    expect(listener.mock.calls).toEqual([["abc"], [null]]);
  });

  it("says nothing when the token is set to what it already was", () => {
    setAccessToken("abc");
    const listener = vi.fn();
    subscribeToAccessToken(listener);

    setAccessToken("abc");

    // A re-render for every request that reuses the same token would be an
    // expensive way to say nothing happened.
    expect(listener).not.toHaveBeenCalled();
  });

  it("stops telling a subscriber that unsubscribed", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToAccessToken(listener);

    unsubscribe();
    setAccessToken("abc");

    expect(listener).not.toHaveBeenCalled();
  });

  it("refuses to store a token on the server", () => {
    vi.stubGlobal("window", undefined);

    expect(() => setAccessToken("abc")).toThrow(/only be set in the browser/);
  });
});
