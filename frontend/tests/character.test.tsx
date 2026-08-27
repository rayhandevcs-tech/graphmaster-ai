/**
 * The drawn character, and the three objects the celebration hands over.
 *
 * These replaced flat single-fill shapes and `lucide-react` icons, and the
 * properties that made the replacement worth doing are the ones a later edit
 * would quietly undo: the figure has a body, the shading themes rather than
 * being painted on, and the gradient ids do not collide when two celebrations
 * share a page.
 *
 * One of them is a product requirement rather than a preference. The lowest
 * tier's prop must stay a toy (FR-7.6) — "make it look more realistic" is what
 * started this work, and for that one object it is the wrong answer.
 *
 * **What is deliberately not asserted here.** `TierFlower` provides its own
 * `LazyMotion`, because without one every petal stays at its `scale: 0`
 * initial frame and the flower renders as five creases and nothing else. That
 * cannot be tested in jsdom: no animation runs there, so the DOM is identical
 * with and without a provider. It was found by rendering the page in a real
 * browser and looking at it, which is the only thing that finds it.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AvatarCharacter, avatarCodeFor, avatarCodeFromUrl } from "@/components/avatars/character";
import { TierCrown, TierFlower, TierMallet } from "@/components/gamification/tier-props";

function svgOf(container: HTMLElement): SVGSVGElement {
  const svg = container.querySelector("svg");
  expect(svg).not.toBeNull();
  return svg as SVGSVGElement;
}

describe("which character a profile gets", () => {
  it("prefers the chosen avatar over the gender fallback", () => {
    expect(avatarCodeFor({ avatar: { code: "girl_scholar" }, gender: "male" })).toBe(
      "girl_scholar",
    );
  });

  it("falls back by gender for a profile older than the catalogue", () => {
    expect(avatarCodeFor({ avatar: null, gender: "male" })).toBe("boy_default");
    expect(avatarCodeFor(null)).toBe("girl_default");
  });

  it("reads a code out of a stored path without fetching it", () => {
    // The file has never existed in this repository; the path is an
    // identifier, which is the only reason it is still parsed.
    expect(avatarCodeFromUrl("/avatars/girl-scholar.svg")).toBe("girl_scholar");
    expect(avatarCodeFromUrl("/avatars/unknown-thing.svg")).toBeNull();
    expect(avatarCodeFromUrl(null)).toBeNull();
  });
});

describe("the two builds of the character", () => {
  it("defaults to the bust, which is what every list wants", () => {
    const { container } = render(<AvatarCharacter code="girl_default" />);
    expect(svgOf(container).getAttribute("viewBox")).toBe("0 0 96 96");
  });

  it("draws a taller frame for the figure, so there is room for a body", () => {
    const { container } = render(<AvatarCharacter code="girl_default" variant="figure" />);
    expect(svgOf(container).getAttribute("viewBox")).toBe("0 0 96 140");
  });

  it("gives the figure a ground shadow to stand on", () => {
    const { container } = render(<AvatarCharacter code="boy_default" variant="figure" />);
    // Weight comes from the shadow more than from any shading on the body.
    expect(container.querySelector("ellipse.fill-primary\\/20")).not.toBeNull();
  });

  it("poses the arms, which is what makes a body read as reacting", () => {
    const rest = render(<AvatarCharacter code="boy_default" variant="figure" pose="rest" />);
    const cheer = render(<AvatarCharacter code="boy_default" variant="figure" pose="cheer" />);
    const restArms = svgOf(rest.container).innerHTML;
    const cheerArms = svgOf(cheer.container).innerHTML;
    expect(restArms).not.toBe(cheerArms);
  });

  it("is hidden from a screen reader unless it is given a name", () => {
    const { container } = render(<AvatarCharacter code="boy_default" />);
    expect(svgOf(container).getAttribute("aria-hidden")).toBe("true");

    render(<AvatarCharacter code="boy_default" title="Your character" />);
    expect(screen.getByRole("img", { name: "Your character" })).toBeInTheDocument();
  });
});

describe("shading that survives a theme", () => {
  it("paints every gradient stop with currentColor rather than a colour", () => {
    const { container } = render(<AvatarCharacter code="girl_scholar" variant="figure" />);
    const stops = [...container.querySelectorAll("stop")];

    expect(stops.length).toBeGreaterThan(0);
    // A painted highlight looks right in whichever theme its author had open.
    // Both stops being `currentColor` makes a gradient a *shape of light*,
    // which is what lets one drawing work on both grounds.
    for (const stop of stops) {
      expect(stop.getAttribute("stop-color")).toBe("currentColor");
    }
  });

  it("does not collide when two characters share a page", () => {
    const { container } = render(
      <div>
        <AvatarCharacter code="girl_default" variant="figure" />
        <AvatarCharacter code="boy_default" variant="figure" />
      </div>,
    );
    const ids = [...container.querySelectorAll("linearGradient")].map((node) => node.id);

    expect(ids.length).toBeGreaterThan(2);
    // A hard-coded id would make the second character paint with the first
    // one's gradient — a bug that only appears once two are on screen.
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("the three tier props", () => {
  it.each([
    ["crown", TierCrown],
    ["flower", TierFlower],
    ["mallet", TierMallet],
  ])("draws the %s with more than one plane", (_name, Prop) => {
    const { container } = render(<Prop />);
    const shaded = container.querySelectorAll(
      '[fill-opacity], [fill^="url("], [stop-color="currentColor"]',
    );
    // A single flat fill is a silhouette, and a silhouette has no volume no
    // matter how detailed its outline is.
    expect(shaded.length).toBeGreaterThan(1);
  });

  it.each([
    ["crown", TierCrown],
    ["flower", TierFlower],
    ["mallet", TierMallet],
  ])("keeps the %s out of the accessibility tree", (_name, Prop) => {
    const { container } = render(<Prop />);
    expect(svgOf(container).getAttribute("aria-hidden")).toBe("true");
  });

  it("keeps the mallet a toy rather than a tool (FR-7.6)", () => {
    const { container } = render(<TierMallet />);
    const widths = [...container.querySelectorAll("rect")].map((node) =>
      Number(node.getAttribute("width")),
    );
    const head = Math.max(...widths);
    const handle = Math.min(...widths);

    // Comic proportions are the requirement rather than the styling. A head
    // four times the width of its own handle cannot read as a claw hammer
    // swinging at a student who scored badly — which is the one thing this
    // prop must never become, however "realistic" the rest of the work gets.
    expect(head / handle).toBeGreaterThan(4);

    const headRect = [...container.querySelectorAll("rect")].find(
      (node) => Number(node.getAttribute("width")) === head,
    );
    // Round-cornered, not a machined block.
    expect(Number(headRect!.getAttribute("rx"))).toBeGreaterThanOrEqual(8);
  });
});
