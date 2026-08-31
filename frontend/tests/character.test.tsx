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
  // The frames are asserted by shape rather than by their exact numbers. A
  // redraw changes the units and breaks a literal `viewBox` assertion while
  // changing nothing a reader would notice, which makes the literal a tax on
  // every future redraw rather than a guarantee.
  const frameOf = (container: HTMLElement) => {
    const [, , width, height] = (svgOf(container).getAttribute("viewBox") ?? "")
      .split(/\s+/)
      .map(Number);
    return { width: width as number, height: height as number };
  };

  it("defaults to the bust, which is what every list wants", () => {
    const { container } = render(<AvatarCharacter code="girl_default" />);
    const { width, height } = frameOf(container);
    // Square: a bust sits in a round or square slot in every list that uses it.
    expect(width).toBe(height);
  });

  it("draws a taller frame for the figure, so there is room for a body", () => {
    const { container } = render(<AvatarCharacter code="girl_default" variant="figure" />);
    const { width, height } = frameOf(container);
    expect(height).toBeGreaterThan(width * 1.4);
  });

  it("lets the celebration own the shadow, which the figure must not carry", () => {
    // The stage draws its own shadow as a sibling so it can spread on an
    // impact while the body squashes. Two shadows is the visible bug; a shadow
    // that rotates with a falling body is the worse invisible one.
    const { container } = render(
      <AvatarCharacter code="boy_default" variant="figure" groundShadow={false} />,
    );
    expect(container.querySelector("ellipse.fill-primary\\/20")).toBeNull();
  });

  it("draws a whole face per expression rather than mixing parts", () => {
    // Surprise is the crown's landing beat and nothing else uses it; if it
    // rendered the same face as `happy` the beat would not exist.
    const happy = render(
      <AvatarCharacter code="boy_default" variant="figure" expression="happy" />,
    );
    const surprised = render(
      <AvatarCharacter code="boy_default" variant="figure" expression="surprised" />,
    );
    expect(svgOf(surprised.container).innerHTML).not.toBe(svgOf(happy.container).innerHTML);
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

    // A hard-coded id would make the second character paint with the first
    // one's gradient — a bug that only appears once two are on screen. The
    // count is not the assertion (most of the figure is flat tokens now, and
    // only the shirt still needs a gradient); uniqueness is.
    expect(ids.length).toBeGreaterThanOrEqual(2);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("the three tier props", () => {
  it.each([
    ["crown", TierCrown],
    ["flower", TierFlower],
    ["mallet", TierMallet],
  ])("draws the %s as a sticker: an outline and a lit plane", (_name, Prop) => {
    const { container } = render(<Prop />);

    // The outline. Drawn under the fill with `paint-order: stroke`, which is
    // what puts the whole stroke width outside the shape instead of
    // straddling its edge — and what makes a flat cartoon object read as
    // having weight.
    const outlined = container.querySelector("[stroke-width]");
    expect(outlined).not.toBeNull();
    expect(Number(outlined?.getAttribute("stroke-width"))).toBeGreaterThanOrEqual(3);

    // And a second, lighter plane. One flat fill inside an outline is a
    // sticker of a silhouette; the lit face is what gives it a direction.
    expect(container.querySelector('[class*="fill-card"]')).not.toBeNull();
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
    const svg = svgOf(container);
    const [, , frameWidth, frameHeight] = (svg.getAttribute("viewBox") ?? "")
      .split(/\s+/)
      .map(Number);
    const head = container.querySelector("rect");

    // Comic proportions are the requirement rather than the styling. The head
    // spans most of the frame and is a deep, round-cornered block — nothing
    // shaped like that swings at anyone. A claw hammer's head is a narrow
    // wedge, which is what the drawing must never drift towards, and the
    // reference this was restyled from was an axe.
    expect(Number(head?.getAttribute("width"))).toBeGreaterThan((frameWidth as number) * 0.75);
    expect(Number(head?.getAttribute("height"))).toBeGreaterThan((frameHeight as number) * 0.3);
    expect(Number(head?.getAttribute("rx"))).toBeGreaterThan(8);
  });
});
