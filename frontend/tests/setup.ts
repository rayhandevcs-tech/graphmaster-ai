import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

/**
 * jsdom implements no media queries at all, and `window.matchMedia` is simply
 * absent. Components that ask whether the reader has requested reduced motion
 * call it in their first effect, so without this every one of them throws on
 * mount. The stub answers what a browser with no preference set answers.
 *
 * A test that needs the other answer stubs `window.matchMedia` itself;
 * `vi.restoreAllMocks()` below puts this back afterwards.
 */
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
