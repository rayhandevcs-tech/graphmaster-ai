/**
 * The chart palette, resolved from the stylesheet at runtime.
 *
 * Chart.js paints onto a canvas, and a canvas cannot read `var(--chart-1)` —
 * it needs a concrete colour. Hardcoding one here would defeat the whole point
 * of the token system: the value would be the same on a dark ground, where the
 * light-theme purple is too dim to read, and `tests/design-tokens.test.ts`
 * fails the build for exactly that (NFR-4.2).
 *
 * So the token is resolved by *painting* it. The computed value of an OKLCH
 * custom property is still `oklch(...)`, which Chart.js's colour helper cannot
 * parse when it wants an alpha variant for a fill or a hover state — reading
 * the pixel back gives plain sRGB that everything downstream understands, and
 * it costs one 1×1 canvas for the life of the tab.
 */

/** Keyed by token, theme and alpha: the same token resolves differently per theme. */
const cache = new Map<string, string>();
let probe: CanvasRenderingContext2D | null = null;

function probeContext(): CanvasRenderingContext2D | null {
  if (probe) return probe;
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  // `willReadFrequently` keeps the surface on the CPU — without it every read
  // stalls the GPU pipeline, and a pie chart resolves six colours in a row.
  probe = canvas.getContext("2d", { willReadFrequently: true });
  return probe;
}

function toHex(value: number): string {
  return value.toString(16).padStart(2, "0");
}

/**
 * `--chart-1` and friends, as something a canvas can paint.
 *
 * `alpha` becomes the seventh and eighth hex digit rather than wrapping the
 * value, so the result is a single string Chart.js will neither reparse nor
 * reject.
 */
export function resolveToken(token: string, alpha = 1, themeKey = ""): string {
  const key = `${token}@${themeKey}@${alpha}`;
  const hit = cache.get(key);
  if (hit !== undefined) return hit;

  const declared = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  const context = probeContext();

  // No canvas (jsdom, or a context the browser refused): hand back the declared
  // value. Modern canvases do accept `oklch()`, so this degrades rather than
  // breaks, and an empty string lets Chart.js fall back to its own default.
  if (!context || !declared) return declared;

  context.clearRect(0, 0, 1, 1);
  // A keyword, so an unparseable custom property leaves the context in a state
  // we can detect instead of silently reusing the previous colour.
  context.fillStyle = "transparent";
  context.fillStyle = declared;
  context.fillRect(0, 0, 1, 1);

  const pixel = context.getImageData(0, 0, 1, 1).data;
  if (pixel[3] === 0) return declared;

  const opacity = Math.round(Math.min(Math.max(alpha, 0), 1) * 255);
  const resolved = `#${toHex(pixel[0] ?? 0)}${toHex(pixel[1] ?? 0)}${toHex(pixel[2] ?? 0)}${toHex(opacity)}`;
  cache.set(key, resolved);
  return resolved;
}

/** The six series tokens, in the order Chart.js consumes them. */
export const SERIES_TOKENS = [
  "--chart-1",
  "--chart-2",
  "--chart-3",
  "--chart-4",
  "--chart-5",
  "--chart-6",
] as const;

export function seriesToken(index: number): string {
  return SERIES_TOKENS[index % SERIES_TOKENS.length] as string;
}

/**
 * Everything a chart needs, resolved once per render.
 *
 * `themeKey` is never read for its value — it is part of the cache key, and
 * passing it is what makes a theme switch resolve the palette again instead of
 * reusing the memoised one.
 */
export function chartPalette(themeKey: string) {
  return {
    series: (index: number, alpha = 1) => resolveToken(seriesToken(index), alpha, themeKey),
    foreground: resolveToken("--foreground", 1, themeKey),
    muted: resolveToken("--muted-foreground", 1, themeKey),
    border: resolveToken("--border", 1, themeKey),
    card: resolveToken("--card", 1, themeKey),
  };
}

export type ChartPalette = ReturnType<typeof chartPalette>;

/** Test seam: a theme switch in jsdom keeps no stale resolution. */
export function resetPaletteCache(): void {
  cache.clear();
  probe = null;
}
