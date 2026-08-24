/**
 * The palette rules, enforced rather than remembered.
 *
 * Two of them are the kind that decay quietly. A hex code pasted into a
 * component looks right in whichever theme the author had open and wrong in
 * the other one, and nobody notices until a marker opens the app in dark mode.
 * And gold stops meaning "crown" the moment it appears on a save button — the
 * reward animation still plays, it just no longer feels earned.
 *
 * This walks the source the way the backend's API-surface test walks the
 * OpenAPI document: the rule is a list in this file, and relaxing it means
 * adding a line with a reason.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(import.meta.dirname, "..");
const STYLESHEET = path.join(ROOT, "app", "globals.css");
const SOURCE_DIRS = ["app", "components", "lib"];

/**
 * Gold is reserved for the crown tier, the XP bar and the level-up moment.
 * A file that needs it belongs under one of these.
 */
const MAY_USE_GOLD = ["app/globals.css", "components/gamification/", "components/ui/badge.tsx"];

const COLOUR_LITERAL =
  /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|\b(?:rgba?|hsla?|oklch|oklab)\(/;

const GOLD_UTILITY = /\b(?:bg|text|border|ring|from|to|via|fill|stroke)-(?:gold|tier-crown)\b/;

function sourceFiles(): string[] {
  const found: string[] = [];

  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const full = path.join(dir, entry);
      if (statSync(full).isDirectory()) {
        walk(full);
      } else if (/\.(tsx?|css)$/.test(entry)) {
        found.push(path.relative(ROOT, full));
      }
    }
  };

  for (const dir of SOURCE_DIRS) walk(path.join(ROOT, dir));
  return found.sort();
}

/** The custom properties declared in one selector block of `globals.css`. */
function tokensIn(selector: string): Map<string, string> {
  const css = readFileSync(STYLESHEET, "utf8");
  const start = css.indexOf(`${selector} {`);
  expect(start, `${selector} block missing from globals.css`).toBeGreaterThan(-1);

  const body = css.slice(start, css.indexOf("\n}", start));
  const tokens = new Map<string, string>();
  for (const match of body.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) {
    tokens.set(match[1] as string, (match[2] as string).trim());
  }
  return tokens;
}

describe("the palette", () => {
  it("defines every colour for both themes", () => {
    const light = tokensIn(":root");
    const dark = tokensIn(".dark");

    // Only the ones that carry a colour of their own — a token defined as
    // `var(--foreground)` follows whatever that resolves to.
    const colours = [...light]
      .filter(([, value]) => value.includes("oklch("))
      .map(([name]) => name);

    expect(colours.length).toBeGreaterThan(20);
    expect(colours.filter((name) => !dark.has(name))).toEqual([]);
  });

  it("names the tiers, the reserved gold and the chart series", () => {
    const light = tokensIn(":root");

    for (const token of [
      "--primary",
      "--secondary",
      "--gold",
      "--tier-crown",
      "--tier-flower",
      "--tier-steady",
      "--tier-hammer",
      "--chart-1",
    ]) {
      expect(light.has(token), `${token} is not defined`).toBe(true);
    }
  });

  it("keeps gold out of the ordinary interface", () => {
    const offenders = sourceFiles().filter((file) => {
      if (MAY_USE_GOLD.some((allowed) => file.startsWith(allowed))) return false;
      return GOLD_UTILITY.test(readFileSync(path.join(ROOT, file), "utf8"));
    });

    // If a new file needs gold, it belongs to the reward surfaces — add it to
    // MAY_USE_GOLD with a reason, or use `primary`.
    expect(offenders, "gold is reserved for the reward surfaces").toEqual([]);
  });

  it("has no hardcoded colours outside the stylesheet", () => {
    const offenders = sourceFiles()
      .filter((file) => file !== "app/globals.css")
      .filter((file) => COLOUR_LITERAL.test(readFileSync(path.join(ROOT, file), "utf8")));

    // A literal is invisible to the theme: it is the same colour on a dark
    // ground, where it may be unreadable, and it cannot be retuned centrally.
    expect(offenders, "every colour comes from a token (NFR-4.2)").toEqual([]);
  });
});
