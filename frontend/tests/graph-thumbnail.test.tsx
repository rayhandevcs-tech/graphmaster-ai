/**
 * The picture on a practice card.
 *
 * These assert what the drawing *says*, not its path data. A test that pins
 * exact coordinates fails on every adjustment to padding and passes on every
 * change that actually matters — a series drawn across a gap, a bar measured
 * from its own minimum — so the assertions here are about counts, baselines
 * and which shapes appear at all.
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GraphThumbnail } from "@/components/practice/graph-thumbnail";

const svgOf = (container: HTMLElement) => container.querySelector("svg") as SVGSVGElement;
const paths = (container: HTMLElement) => [...container.querySelectorAll("path")];

describe("the graph thumbnail", () => {
  it("draws one line per series", () => {
    const { container } = render(
      <GraphThumbnail
        graphType="line"
        preview={{
          series: [
            [1, 2, 3],
            [3, 2, 1],
          ],
        }}
      />,
    );
    expect(paths(container)).toHaveLength(2);
  });

  it("breaks a line at a gap rather than drawing across it", () => {
    // A line that closes over a missing reading is a different graph, and it
    // is the one a student would then be describing.
    const solid = render(<GraphThumbnail graphType="line" preview={{ series: [[1, 2, 3, 4]] }} />);
    const gapped = render(
      <GraphThumbnail graphType="line" preview={{ series: [[1, 2, null, 4]] }} />,
    );

    expect(paths(solid.container)).toHaveLength(1);
    expect(paths(gapped.container)).toHaveLength(2);
  });

  it("measures bars from zero, not from the series minimum", () => {
    // 98 → 100 is a small rise. Measured from its own minimum it becomes a
    // full-height column beside a sliver, which is a lie about the data.
    const { container } = render(
      <GraphThumbnail graphType="bar" preview={{ series: [[98, 99, 100]] }} />,
    );
    const heights = [...container.querySelectorAll("rect")].map((rect) =>
      Number(rect.getAttribute("height")),
    );

    expect(heights).toHaveLength(3);
    // All three bars are nearly as tall as each other, because they nearly
    // are. The shortest is at least four fifths of the tallest.
    expect(Math.min(...heights)).toBeGreaterThan(Math.max(...heights) * 0.8);
  });

  it("gives a zero bar a visible stub rather than nothing", () => {
    const { container } = render(
      <GraphThumbnail graphType="bar" preview={{ series: [[0, 10]] }} />,
    );
    const heights = [...container.querySelectorAll("rect")].map((rect) =>
      Number(rect.getAttribute("height")),
    );
    // A zero drawn as no bar at all is indistinguishable from missing data.
    expect(Math.min(...heights)).toBeGreaterThan(0);
  });

  it("draws one slice per positive value, and a whole circle for a single one", () => {
    const three = render(<GraphThumbnail graphType="pie" preview={{ series: [[1, 1, 2]] }} />);
    expect(paths(three.container)).toHaveLength(3);

    // A wedge from a point back to itself draws nothing, so the single-slice
    // case is a circle rather than an arc.
    const one = render(<GraphThumbnail graphType="pie" preview={{ series: [[5]] }} />);
    expect(paths(one.container)).toHaveLength(1);
    expect(paths(one.container)[0]?.getAttribute("d")).toContain("a");
  });

  it("drops values a pie cannot show rather than sweeping them backwards", () => {
    const { container } = render(
      <GraphThumbnail graphType="pie" preview={{ series: [[5, -2, 5]] }} />,
    );
    expect(paths(container)).toHaveLength(2);
  });

  it("fills the area under a line only when the graph is an area chart", () => {
    const line = render(<GraphThumbnail graphType="line" preview={{ series: [[1, 4, 2]] }} />);
    const area = render(<GraphThumbnail graphType="area" preview={{ series: [[1, 4, 2]] }} />);

    expect(paths(line.container)).toHaveLength(1);
    expect(paths(area.container)).toHaveLength(2);
  });

  it("draws an empty frame when the figures cannot be read", () => {
    // The API sends `preview: null` for a blob it could not parse. An empty
    // box in a grid of pictures reads as a card still loading, and a student
    // waits for it — so something is always drawn.
    for (const preview of [null, undefined, { series: [] }, { series: [[null, null]] }]) {
      const { container } = render(<GraphThumbnail graphType="line" preview={preview} />);
      expect(svgOf(container)).not.toBeNull();
      expect(container.querySelectorAll("path").length).toBeGreaterThan(0);
    }
  });

  it("is hidden from screen readers, because the title and task carry it", () => {
    const { container } = render(
      <GraphThumbnail graphType="line" preview={{ series: [[1, 2]] }} />,
    );
    expect(svgOf(container).getAttribute("aria-hidden")).toBe("true");
  });
});
