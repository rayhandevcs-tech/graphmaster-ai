import type { ChartConfiguration, ChartType as ChartJsType, TooltipItem } from "chart.js";

import type { GraphType } from "@/types/api";
import type { ChartPalette } from "./palette";
import { formatValue, type NormalisedChart } from "./normalise";

/**
 * The Chart.js configuration, built away from the canvas so it can be asserted
 * on in a test. Every colour is a resolved token — see `palette.ts` for why
 * that resolution happens at runtime rather than as a literal here.
 */

/** `area` is a line chart that fills; Chart.js has no separate controller. */
export function controllerFor(graphType: GraphType): ChartJsType {
  switch (graphType) {
    case "bar":
      return "bar";
    case "pie":
      return "pie";
    default:
      return "line";
  }
}

const FONT_FAMILY =
  "var(--font-inter), ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif";

export interface BuildArgs {
  chart: NormalisedChart;
  graphType: GraphType;
  palette: ChartPalette;
  /** False under `prefers-reduced-motion`, which the student's OS decides. */
  animate: boolean;
}

export function buildChartConfig({
  chart,
  graphType,
  palette,
  animate,
}: BuildArgs): ChartConfiguration {
  const type = controllerFor(graphType);
  const isPie = type === "pie";
  const showLegend = isPie || chart.series.length > 1;

  const label = (item: TooltipItem<ChartJsType>) => {
    // `parsed` is a number for an arc and a point for a cartesian chart, so
    // across the controller union Chart.js types it as `never`. The shape is
    // decided by the controller chosen above, not by the caller.
    const parsed = item.parsed as number | { y?: number | null } | null;
    const value = typeof parsed === "number" ? parsed : (parsed?.y ?? null);
    const name = isPie ? item.label : item.dataset.label;
    return `${name}: ${formatValue(value, chart.unit)}`;
  };

  return {
    type,
    data: {
      labels: chart.labels,
      datasets: chart.series.map((series, index) => ({
        label: series.label,
        data: series.data,
        ...seriesStyle({ graphType, index, palette, chart }),
        // The teacher's own styling wins: the API stores it verbatim precisely
        // so a series can be styled without a schema change.
        ...series.styling,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: animate ? { duration: 600 } : false,
      // Points are small; a generous hit area is what makes the tooltip
      // reachable on a phone.
      interaction: { mode: isPie ? "nearest" : "index", intersect: false },
      layout: { padding: { top: 4, right: 4, bottom: 0, left: 0 } },
      plugins: {
        legend: {
          display: showLegend,
          position: isPie ? "right" : "top",
          align: "start",
          labels: {
            color: palette.muted,
            boxWidth: 10,
            boxHeight: 10,
            usePointStyle: true,
            pointStyle: "circle",
            font: { family: FONT_FAMILY, size: 12 },
          },
        },
        tooltip: {
          backgroundColor: palette.foreground,
          titleColor: palette.card,
          bodyColor: palette.card,
          borderColor: palette.border,
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          displayColors: !isPie,
          titleFont: { family: FONT_FAMILY, size: 12, weight: 600 },
          bodyFont: { family: FONT_FAMILY, size: 12 },
          callbacks: { label },
        },
      },
      scales: isPie
        ? undefined
        : {
            x: {
              title: axisTitle(chart.xAxisLabel, palette),
              grid: { display: false },
              border: { color: palette.border },
              ticks: { color: palette.muted, font: { family: FONT_FAMILY, size: 11 } },
            },
            y: {
              // Not `beginAtZero`. An axis forced to zero flattens a series that
              // moves between 230 and 250 into a straight line, and describing
              // exactly that movement is the exercise.
              title: axisTitle(chart.yAxisLabel, palette),
              grid: { color: palette.border, drawTicks: false },
              border: { display: false },
              ticks: {
                color: palette.muted,
                padding: 8,
                font: { family: FONT_FAMILY, size: 11 },
                callback: (value: string | number) =>
                  formatValue(typeof value === "number" ? value : Number(value), chart.unit),
              },
            },
          },
    },
  } as ChartConfiguration;
}

function axisTitle(text: string | null, palette: ChartPalette) {
  return {
    display: Boolean(text),
    text: text ?? "",
    color: palette.muted,
    font: { family: FONT_FAMILY, size: 11, weight: 500 as const },
  };
}

function seriesStyle({
  graphType,
  index,
  palette,
  chart,
}: {
  graphType: GraphType;
  index: number;
  palette: ChartPalette;
  chart: NormalisedChart;
}): Record<string, unknown> {
  if (graphType === "pie") {
    return {
      // A pie's colours vary by *segment*, not by series.
      backgroundColor: chart.labels.map((_, segment) => palette.series(segment)),
      borderColor: palette.card,
      borderWidth: 2,
      hoverOffset: 6,
    };
  }

  if (graphType === "bar") {
    return {
      backgroundColor: palette.series(index, 0.85),
      hoverBackgroundColor: palette.series(index),
      borderRadius: 6,
      borderSkipped: false,
      maxBarThickness: 56,
    };
  }

  return {
    borderColor: palette.series(index),
    backgroundColor: palette.series(index, graphType === "area" ? 0.16 : 1),
    fill: graphType === "area",
    tension: 0.35,
    borderWidth: 2,
    pointRadius: 3,
    pointHoverRadius: 6,
    pointBackgroundColor: palette.series(index),
    pointBorderColor: palette.card,
    pointBorderWidth: 2,
    // Otherwise a null reading joins its neighbours with a straight line, which
    // asserts a value that was never measured.
    spanGaps: false,
  };
}
