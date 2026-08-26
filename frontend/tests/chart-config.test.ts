/**
 * What reaches Chart.js.
 *
 * Two of these assertions guard product decisions rather than code: a y-axis
 * that is not forced to zero, because a series moving between 230 and 250 is
 * exactly what the student is being asked to describe; and gaps that are not
 * spanned, because joining across a missing reading draws a value nobody
 * measured.
 */

import { describe, expect, it } from "vitest";

import { buildChartConfig, controllerFor } from "@/lib/charts/config";
import { describeChart, formatValue, normaliseChart } from "@/lib/charts/normalise";
import type { ChartConfiguration } from "chart.js";

import type { ChartData, GraphType } from "@/types/api";

const palette = {
  series: (index: number, alpha = 1) => `series-${index}-${alpha}`,
  foreground: "fg",
  muted: "muted",
  border: "border",
  card: "card",
};

const DATA: ChartData = {
  labels: ["Jan", "Feb", "Mar"],
  datasets: [{ label: "Revenue", data: [10, null, 30] }],
  x_axis_label: "Month",
  y_axis_label: "Revenue",
  unit: "%",
};

/**
 * One axis, narrowed.
 *
 * Chart.js types `scales` as a union across every scale kind it ships, and a
 * radial scale has no `title` — so reading one needs the cartesian shape
 * asserted. The controller two lines up is what decides it.
 */
function axis(configuration: ChartConfiguration, name: "x" | "y") {
  return configuration.options?.scales?.[name] as
    { title?: { display?: boolean; text?: string } } | undefined;
}

function config(graphType: GraphType, data: ChartData = DATA) {
  return buildChartConfig({
    chart: normaliseChart(data),
    graphType,
    palette,
    animate: false,
  });
}

describe("choosing a controller", () => {
  it.each([
    ["line", "line"],
    ["bar", "bar"],
    ["pie", "pie"],
    // Chart.js has no area controller; an area chart is a line that fills.
    ["area", "line"],
  ] as const)("%s renders as %s", (graphType, expected) => {
    expect(controllerFor(graphType)).toBe(expected);
  });

  it("fills only for an area chart", () => {
    expect(config("area").data.datasets[0]).toMatchObject({ fill: true });
    expect(config("line").data.datasets[0]).toMatchObject({ fill: false });
  });
});

describe("the axes", () => {
  it("does not force the y-axis to zero", () => {
    const scales = config("line").options?.scales;

    expect(scales?.y).toBeDefined();
    expect(scales?.y).not.toHaveProperty("beginAtZero", true);
  });

  it("has no scales at all for a pie", () => {
    expect(config("pie").options?.scales).toBeUndefined();
  });

  it("titles the axes from the chart data", () => {
    const bar = config("bar");

    expect(axis(bar, "x")?.title).toMatchObject({ display: true, text: "Month" });
    expect(axis(bar, "y")?.title).toMatchObject({ display: true, text: "Revenue" });
  });

  it("hides an axis title the teacher did not set", () => {
    const bare = config("line", { labels: ["a"], datasets: [{ label: "s", data: [1] }] });

    expect(axis(bare, "x")?.title).toMatchObject({ display: false });
  });
});

describe("the series", () => {
  it("does not join across a missing reading", () => {
    expect(config("line").data.datasets[0]).toMatchObject({ spanGaps: false });
  });

  it("colours a pie by segment, not by series", () => {
    // Three labels, one dataset: three colours.
    expect(config("pie").data.datasets[0]?.backgroundColor).toHaveLength(3);
  });

  it("lets the teacher's own styling win over the themed default", () => {
    // The API stores extra dataset keys verbatim so a series can be styled
    // without a schema change; applying them last is what honours that.
    const styled = config("line", {
      ...DATA,
      datasets: [{ label: "Revenue", data: [1, 2, 3], borderDash: [4, 4], tension: 0 }],
    });

    expect(styled.data.datasets[0]).toMatchObject({ borderDash: [4, 4], tension: 0 });
  });

  it("shows a legend only when there is more than one series", () => {
    const single = config("line");
    const double = config("line", {
      ...DATA,
      datasets: [
        { label: "A", data: [1, 2, 3] },
        { label: "B", data: [3, 2, 1] },
      ],
    });

    expect(single.options?.plugins?.legend?.display).toBe(false);
    expect(double.options?.plugins?.legend?.display).toBe(true);
    // A pie's legend is the only key to which slice is which.
    expect(config("pie").options?.plugins?.legend?.display).toBe(true);
  });
});

describe("reduced motion", () => {
  it("switches the animation off entirely rather than shortening it", () => {
    const still = buildChartConfig({
      chart: normaliseChart(DATA),
      graphType: "line",
      palette,
      animate: false,
    });

    expect(still.options?.animation).toBe(false);
  });
});

describe("normalising what the teacher stored", () => {
  it("separates styling from the data it decorates", () => {
    const chart = normaliseChart({
      labels: ["a"],
      datasets: [{ label: "S", data: [1], borderDash: [2, 2] }],
    });

    expect(chart.series[0]?.data).toEqual([1]);
    expect(chart.series[0]?.styling).toEqual({ borderDash: [2, 2] });
  });

  it("treats a non-finite reading as missing rather than as zero", () => {
    const chart = normaliseChart({
      labels: ["a", "b"],
      datasets: [{ label: "S", data: [Number.NaN as unknown as number, 2] }],
    });

    expect(chart.series[0]?.data).toEqual([null, 2]);
  });

  it("reports a chart with no rows as empty rather than throwing", () => {
    expect(normaliseChart({ labels: [], datasets: [] }).isEmpty).toBe(true);
    expect(normaliseChart(null).isEmpty).toBe(true);
    expect(normaliseChart(undefined).isEmpty).toBe(true);
  });

  it("names an unlabelled series rather than rendering a blank legend", () => {
    const chart = normaliseChart({ labels: ["a"], datasets: [{ label: "", data: [1] }] });

    expect(chart.series[0]?.label).toBe("Series 1");
  });
});

describe("formatting a value", () => {
  it("attaches a symbol unit tightly and a word unit loosely", () => {
    expect(formatValue(48, "%")).toBe("48%");
    expect(formatValue(48, "students")).toBe("48 students");
    expect(formatValue(48, null)).toBe("48");
  });

  it("shows a missing reading as a dash, never as zero", () => {
    expect(formatValue(null, "%")).toBe("—");
  });
});

describe("describing a chart for a screen reader", () => {
  it("gives the shape and scope, and points at the table for the figures", () => {
    const description = describeChart(normaliseChart(DATA), "line", "Monthly revenue");

    expect(description).toContain("Monthly revenue");
    expect(description).toContain("one series, Revenue");
    expect(description).toContain("from Jan to Mar");
    expect(description).toContain("data table");
    // Not the numbers: twelve readings as one label is worse than no label.
    expect(description).not.toContain("10");
  });

  it("says so plainly when there is nothing to describe", () => {
    expect(describeChart(normaliseChart(null), "bar", "Empty")).toContain("no data");
  });
});
