"use client";

import { useId, useMemo, useState } from "react";
import { Table2 } from "lucide-react";

import { GraphChart } from "./graph-chart";
import { ChartDataTable } from "./chart-data-table";
import { normaliseChart } from "@/lib/charts/normalise";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChartData, GraphType } from "@/types/api";

/**
 * A chart with its figures one click away.
 *
 * The toggle is not only an accessibility affordance: a student describing a
 * line has to read values off it, and squinting at a canvas is a worse way to
 * do that than reading the table. Sighted students use this constantly.
 */
export function ChartPanel({
  chartData,
  graphType,
  title,
  height = "h-[18rem] sm:h-[22rem]",
  className,
}: {
  chartData: ChartData;
  graphType: GraphType;
  title: string;
  /** Tailwind height classes for the canvas box — the panel itself is fluid. */
  height?: string;
  className?: string;
}) {
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();
  const chart = useMemo(() => normaliseChart(chartData), [chartData]);

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className={cn("w-full", height)}>
        <GraphChart chartData={chartData} graphType={graphType} title={title} />
      </div>

      {chart.isEmpty ? null : (
        <div className="flex flex-col gap-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-expanded={showTable}
            aria-controls={tableId}
            onClick={() => setShowTable((open) => !open)}
            className="text-muted-foreground hover:text-foreground -ml-2 w-fit"
          >
            <Table2 aria-hidden />
            {showTable ? "Hide data table" : "Show data table"}
          </Button>

          <div id={tableId}>
            <ChartDataTable
              chart={chart}
              caption={`The figures behind ${title}${chart.unit ? `, in ${chart.unit}` : ""}.`}
              visible={showTable}
            />
          </div>
        </div>
      )}
    </div>
  );
}
