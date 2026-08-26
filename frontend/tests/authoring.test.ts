/**
 * Authoring a graph, and the table a teacher pastes into it.
 *
 * The round trip is the property that matters: open an existing graph, see the
 * table that produced it, change one number, and get the same chart back with
 * that one number different. A blank cell must survive as blank — a zero
 * invented here becomes a data point a student is asked to describe.
 */

import { describe, expect, it } from "vitest";

import { parseTable, toTableText } from "@/lib/charts/table-text";

describe("reading a pasted table", () => {
  it("takes the first line as the series names and the rest as points", () => {
    const { chartData, problems } = parseTable("Label, Rainfall\nJan, 42\nFeb, 51");

    expect(problems).toEqual([]);
    expect(chartData.labels).toEqual(["Jan", "Feb"]);
    expect(chartData.datasets).toHaveLength(1);
    expect(chartData.datasets[0]?.label).toBe("Rainfall");
    expect(chartData.datasets[0]?.data).toEqual([42, 51]);
  });

  it("accepts a spreadsheet paste, which arrives tab-separated", () => {
    const { chartData } = parseTable("Label\tSales\tCosts\nQ1\t120\t80");

    expect(chartData.datasets.map((set) => set.label)).toEqual(["Sales", "Costs"]);
    expect(chartData.datasets[1]?.data).toEqual([80]);
  });

  it("keeps a blank cell blank rather than inventing a zero", () => {
    const { chartData } = parseTable("Label, Rainfall\nJan, 42\nFeb,\nMar, 30");

    expect(chartData.datasets[0]?.data).toEqual([42, null, 30]);
  });

  it("reads a thousands separator inside a cell", () => {
    const { chartData } = parseTable("Label\tSales\nQ1\t1,240");
    expect(chartData.datasets[0]?.data).toEqual([1240]);
  });

  it("says what is missing rather than producing half a chart", () => {
    expect(parseTable("").problems[0]).toMatch(/header row/i);
    expect(parseTable("Label\nJan, 4").problems[0]).toMatch(/name for at least one series/i);
    expect(parseTable("Label, Rainfall").problems[0]).toMatch(/at least one row/i);
  });

  it("carries the axis labels and the unit through", () => {
    const { chartData } = parseTable("Label, Rainfall\nJan, 42", {
      x: "Month",
      y: "Rainfall",
      unit: "mm",
    });

    expect(chartData.x_axis_label).toBe("Month");
    expect(chartData.y_axis_label).toBe("Rainfall");
    expect(chartData.unit).toBe("mm");
  });
});

describe("the round trip", () => {
  it("renders a stored chart as the table that would produce it", () => {
    const text = toTableText({
      labels: ["Jan", "Feb"],
      datasets: [
        { label: "Rainfall", data: [42, null] },
        { label: "Sunshine", data: [3, 5] },
      ],
    });

    expect(text).toBe("Label, Rainfall, Sunshine\nJan, 42, 3\nFeb, , 5");
  });

  it("survives a trip out and back unchanged", () => {
    const original = {
      labels: ["Jan", "Feb", "Mar"],
      datasets: [{ label: "Rainfall", data: [42, null, 30] }],
      x_axis_label: null,
      y_axis_label: null,
      unit: null,
    };

    expect(parseTable(toTableText(original)).chartData).toEqual(original);
  });

  it("renders an empty chart as an empty table, not as a header with no rows", () => {
    expect(toTableText({ labels: [], datasets: [] })).toBe("");
    expect(toTableText(null)).toBe("");
  });
});
