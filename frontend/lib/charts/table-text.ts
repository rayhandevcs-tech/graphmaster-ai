import type { ChartData } from "@/types/api";

/**
 * Chart data as something a teacher can paste.
 *
 * The alternative — a grid of forty small inputs — is where this kind of
 * authoring screen usually ends up, and it is worse in every way that matters
 * here. The figures for a practice graph already exist in a spreadsheet or a
 * table in a textbook, so the fastest correct path is to paste them: the first
 * line names the series, every line after it is a label and its values.
 *
 * Both directions are pure and tested, which is what makes the round trip
 * safe — a teacher opens an existing graph, sees exactly the table that
 * produced it, and edits one number.
 */

/** A blank value keeps its place in the row and becomes `null`, not `0`. */
function parseCell(cell: string): number | null {
  const trimmed = cell.trim();
  if (trimmed === "") return null;
  const value = Number(trimmed.replace(/,/g, ""));
  return Number.isFinite(value) ? value : null;
}

function splitRow(line: string): string[] {
  // Tabs come from a spreadsheet paste, commas from a typed table.
  return line.includes("\t") ? line.split("\t") : line.split(",");
}

export interface ParsedTable {
  chartData: ChartData;
  /** What is wrong, in the teacher's words. Empty when the table is usable. */
  problems: string[];
}

export function parseTable(
  text: string,
  axes: { x?: string; y?: string; unit?: string } = {},
): ParsedTable {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    return {
      chartData: empty(axes),
      problems: ["Add a header row naming the series, then one row per label."],
    };
  }

  if (lines.length === 1) {
    // A header on its own is a different mistake from an empty box, and the
    // teacher is one line away from a usable table — say which line.
    const columns = splitRow(lines[0] as string).filter((cell) => cell.trim() !== "").length;
    return {
      chartData: empty(axes),
      problems: [
        columns >= 2
          ? "Add at least one row of values beneath the header."
          : "Add a header row naming the series, then one row per label.",
      ],
    };
  }

  const header = splitRow(lines[0] as string).map((cell) => cell.trim());
  const seriesNames = header.slice(1).filter((name) => name.length > 0);

  if (seriesNames.length === 0) {
    return {
      chartData: empty(axes),
      problems: ["The header row needs a name for at least one series after the first column."],
    };
  }

  const labels: string[] = [];
  const columns: (number | null)[][] = seriesNames.map(() => []);
  const problems: string[] = [];

  for (const line of lines.slice(1)) {
    const cells = splitRow(line);
    const label = (cells[0] ?? "").trim();
    if (label === "") {
      problems.push("A row has no label in its first column.");
      continue;
    }
    labels.push(label);
    seriesNames.forEach((_, index) => {
      (columns[index] as (number | null)[]).push(parseCell(cells[index + 1] ?? ""));
    });
  }

  if (labels.length === 0) problems.push("Add at least one row of values.");

  return {
    chartData: {
      labels,
      datasets: seriesNames.map((label, index) => ({
        label,
        data: columns[index] ?? [],
      })),
      x_axis_label: axes.x ?? null,
      y_axis_label: axes.y ?? null,
      unit: axes.unit ?? null,
    },
    problems,
  };
}

/** The stored chart, back as the table that would produce it. */
export function toTableText(chart: ChartData | null | undefined): string {
  if (!chart || !Array.isArray(chart.labels) || chart.labels.length === 0) return "";

  const datasets = Array.isArray(chart.datasets) ? chart.datasets : [];
  const header = ["Label", ...datasets.map((set) => set.label)].join(", ");

  const rows = chart.labels.map((label, index) =>
    [label, ...datasets.map((set) => set.data?.[index] ?? "")].join(", "),
  );

  return [header, ...rows].join("\n");
}

function empty(axes: { x?: string; y?: string; unit?: string }): ChartData {
  return {
    labels: [],
    datasets: [],
    x_axis_label: axes.x ?? null,
    y_axis_label: axes.y ?? null,
    unit: axes.unit ?? null,
  };
}
