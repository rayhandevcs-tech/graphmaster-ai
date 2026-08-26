"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "next-themes";
import type { Chart } from "chart.js";

import { buildChartConfig } from "@/lib/charts/config";
import { chartPalette } from "@/lib/charts/palette";
import { describeChart, normaliseChart } from "@/lib/charts/normalise";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { ChartData, GraphType } from "@/types/api";

/**
 * Chart.js, loaded on demand and themed from the stylesheet.
 *
 * Three things here are deliberate:
 *
 * 1. **The module is imported dynamically and registered selectively.** Not
 *    `chart.js/auto`, which registers every controller in the library the
 *    moment it is imported. Only the pieces this graph type needs enter the
 *    registry.
 * 2. **The chart is rebuilt on a theme change** rather than mutated. Every
 *    colour in the configuration is a resolved token and half of them sit
 *    inside nested plugin options — reaching in to patch each one is how a
 *    tooltip ends up with the last theme's border.
 * 3. **The canvas is `aria-hidden`.** It is a bitmap; the figures live in the
 *    data table beside it, which is in the accessibility tree whether or not
 *    it is visible.
 */
export function GraphChart({
  chartData,
  graphType,
  title,
  className,
}: {
  chartData: ChartData;
  graphType: GraphType;
  /** Used only for the canvas description, never drawn. */
  title: string;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chartRef = useRef<Chart | null>(null);
  const [ready, setReady] = useState(false);

  const { resolvedTheme } = useTheme();
  const reducedMotion = useReducedMotion();
  const chart = useMemo(() => normaliseChart(chartData), [chartData]);

  useEffect(() => {
    if (chart.isEmpty) return;

    let cancelled = false;

    void (async () => {
      const chartjs = await import("chart.js");
      const canvas = canvasRef.current;
      // The import can resolve after a fast navigation away.
      if (cancelled || !canvas) return;

      chartjs.Chart.register(...registrationFor(graphType, chartjs));

      chartRef.current?.destroy();
      chartRef.current = new chartjs.Chart(
        canvas,
        buildChartConfig({
          chart,
          graphType,
          // `resolvedTheme` is the cache key, which is what makes a toggle
          // resolve the palette again instead of reusing the memoised one.
          palette: chartPalette(resolvedTheme ?? "light"),
          animate: !reducedMotion,
        }),
      );
      setReady(true);
    })();

    return () => {
      cancelled = true;
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [chart, graphType, resolvedTheme, reducedMotion]);

  if (chart.isEmpty) {
    return (
      <p className="text-muted-foreground flex h-full items-center justify-center text-sm">
        This graph has no data to display.
      </p>
    );
  }

  return (
    <div className={cn("relative h-full w-full", className)}>
      {!ready ? <Skeleton className="absolute inset-0 rounded-lg" /> : null}
      <canvas
        ref={canvasRef}
        aria-hidden
        className={cn("transition-opacity duration-300", ready ? "opacity-100" : "opacity-0")}
      />
      <span className="sr-only">{describeChart(chart, graphType, title)}</span>
    </div>
  );
}

type ChartJsModule = typeof import("chart.js");

/**
 * What each graph type needs in the registry, and nothing more.
 *
 * `area` is a filled line: same controller, plus the Filler plugin. Registering
 * Filler for a plain line would be harmless but misleading — the registry is
 * the honest statement of what this chart can draw.
 */
function registrationFor(graphType: GraphType, chartjs: ChartJsModule) {
  const shared = [chartjs.Tooltip, chartjs.Legend];

  if (graphType === "pie") {
    return [chartjs.PieController, chartjs.ArcElement, ...shared];
  }

  const axes = [chartjs.CategoryScale, chartjs.LinearScale];

  if (graphType === "bar") {
    return [chartjs.BarController, chartjs.BarElement, ...axes, ...shared];
  }

  const line = [chartjs.LineController, chartjs.LineElement, chartjs.PointElement, ...axes];
  return graphType === "area" ? [...line, chartjs.Filler, ...shared] : [...line, ...shared];
}
