/**
 * One avatar system.
 *
 * Six SVGs the catalogue references have never existed in this repository, so
 * every image avatar rendered a 404 and fell back to two grey letters — on the
 * registration step whose entire purpose is choosing a character. The drawn
 * component replaced it; these tests are what stop the old path coming back.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AvatarTileForTests } from "@/components/avatars/avatar-picker";
import type { AvatarWithLock } from "@/types/api";

const ROOT = path.resolve(import.meta.dirname, "..");

function sourceFiles(): string[] {
  const found: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const full = path.join(dir, entry);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.tsx?$/.test(entry)) found.push(path.relative(ROOT, full));
    }
  };
  for (const dir of ["app", "components", "lib"]) walk(path.join(ROOT, dir));
  return found;
}

describe("the avatar system", () => {
  it("has exactly one implementation", () => {
    // `AvatarImage` is gone. Any reappearance is a second system, and the
    // second system is the one that 404s.
    //
    // The scan reads raw text, comments included, so the one file whose
    // comment explains the absence is exempt — the same allowance
    // `design-tokens.test.ts` makes for the files that may use gold.
    const EXPLAINS_THE_RULE = ["components/ui/avatar.tsx"];

    const offenders = sourceFiles().filter(
      (file) =>
        !EXPLAINS_THE_RULE.includes(file) &&
        readFileSync(path.join(ROOT, file), "utf8").includes("AvatarImage"),
    );

    expect(offenders).toEqual([]);
  });

  it("never renders a stored avatar path as an image", () => {
    // `image_url` is an identifier the drawn character is resolved from, and
    // nothing else. `<img src={...image_url}>` is the defect in another shape.
    const offenders = sourceFiles().filter((file) => {
      const source = readFileSync(path.join(ROOT, file), "utf8");
      return /src=\{[^}]*image_url/.test(source);
    });

    expect(offenders).toEqual([]);
  });
});

const avatar = (overrides: Partial<AvatarWithLock> = {}): AvatarWithLock => ({
  id: "00000000-0000-0000-0000-000000000001",
  code: "girl_scholar",
  name: "Nadia the Scholar",
  gender: "female",
  image_url: "/avatars/girl-scholar.svg",
  is_default: false,
  unlock_level: 10,
  is_unlocked: true,
  is_selected: false,
  ...overrides,
});

describe("an avatar tile", () => {
  it("draws the character rather than initials", () => {
    const { container } = render(
      <AvatarTileForTests avatar={avatar()} busy={false} onChoose={vi.fn()} />,
    );

    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(screen.queryByText("NA")).not.toBeInTheDocument();
  });

  it("cannot be locked and selected at once", () => {
    // The impossible pair, sent deliberately. One derived state has no
    // representation for it, so selection wins and the padlock is absent.
    render(
      <AvatarTileForTests
        avatar={avatar({ is_selected: true, is_unlocked: false })}
        busy={false}
        onChoose={vi.fn()}
      />,
    );

    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button")).toBeEnabled();
    expect(screen.queryByText(/Level 10/)).not.toBeInTheDocument();
    expect(screen.queryByText(/locked until/)).not.toBeInTheDocument();
  });

  it("says what a locked one needs, and refuses the click", () => {
    render(
      <AvatarTileForTests
        avatar={avatar({ is_unlocked: false })}
        busy={false}
        onChoose={vi.fn()}
      />,
    );

    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.getByText(/Level 10/)).toBeInTheDocument();
    expect(screen.getByText(/locked until level 10/i)).toBeInTheDocument();
  });

  it("announces the current avatar to a screen reader", () => {
    render(
      <AvatarTileForTests avatar={avatar({ is_selected: true })} busy={false} onChoose={vi.fn()} />,
    );

    expect(screen.getByText(/your current avatar/i)).toBeInTheDocument();
  });
});
