import type { ChartData, ChartDataset, GraphType } from "@/types/api";

/** One series, with the teacher's own Chart.js styling kept separate. */
export interface NormalisedSeries {
  label: string;
  data: (number | null)[];
  /**
   * Everything the teacher put on the dataset besides `label` and `data`.
   *
   * The API stores extra keys verbatim so a series can be styled without a
   * schema change (02-database-schema §3.2). They are applied *after* our
   * themed defaults, so an explicit choice wins — which is the documented
   * intent, and the reason they are not merged blindly into the defaults.
   */
  styling: Record<string, unknown>;
}

export interface NormalisedChart {
  labels: string[];
  series: NormalisedSeries[];
  xAxisLabel: string | null;
  yAxisLabel: string | null;
  unit: string | null;
  /** True when there is nothing to draw — a chart with no rows is not an error. */
  isEmpty: boolean;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asNumberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * `chart_data` as something safe to render.
 *
 * Pydantic already guarantees the shape on the way in, so this is not
 * validation — it is the difference between a malformed row rendering an empty
 * chart and it throwing inside an effect, which takes the whole practice page
 * down with it.
 */
export function normaliseChart(data: ChartData | null | undefined): NormalisedChart {
  const labels = Array.isArray(data?.labels) ? data.labels.map(asString) : [];
  const rawSeries: ChartDataset[] = Array.isArray(data?.datasets) ? data.datasets : [];

  const series = rawSeries.map((dataset, index) => {
    const { label, data: points, ...styling } = dataset;
    return {
      label: asString(label) || `Series ${index + 1}`,
      data: (Array.isArray(points) ? points : []).map(asNumberOrNull),
      styling,
    };
  });

  return {
    labels,
    series,
    xAxisLabel: data?.x_axis_label ?? null,
    yAxisLabel: data?.y_axis_label ?? null,
    unit: data?.unit ?? null,
    isEmpty: labels.length === 0 || series.length === 0,
  };
}

/** `48` and `%` become `48%`; a unit that is a word gets a space. */
export function formatValue(value: number | null, unit: string | null): string {
  if (value === null) return "—";
  const rendered = value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (!unit) return rendered;
  return /^[%°]/.test(unit) ? `${rendered}${unit}` : `${rendered} ${unit}`;
}

/**
 * What a screen-reader user hears in place of the canvas.
 *
 * Deliberately a description of the chart's shape and scope, not its numbers:
 * the numbers are in the data table beneath it, and reading twelve readings
 * aloud as one label is worse than not labelling it at all.
 */
export function describeChart(chart: NormalisedChart, graphType: GraphType, title: string): string {
  if (chart.isEmpty) return `${title}: this chart has no data.`;

  const names = chart.series.map((one) => one.label);
  const seriesPart =
    names.length === 1
      ? `one series, ${names[0]}`
      : `${names.length} series: ${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;

  const axisPart =
    graphType === "pie"
      ? `${chart.labels.length} segments`
      : `${chart.labels.length} points from ${chart.labels[0]} to ${chart.labels[chart.labels.length - 1]}`;

  return `${title}. ${graphType} chart with ${seriesPart}, over ${axisPart}. The same figures follow in a data table.`;
}
