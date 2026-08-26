import { formatValue, type NormalisedChart } from "@/lib/charts/normalise";
import { cn } from "@/lib/utils";

/**
 * The chart's figures as a real table.
 *
 * NFR-4.x requires an alternative to the canvas, and this is only possible
 * because a graph is structured `chart_data` rather than a picture
 * (02-database-schema §3.2) — an image of a chart could not be read out at all.
 *
 * There is one table, not two. Collapsed, it is `sr-only`, so it stays in the
 * accessibility tree while a sighted student sees the chart; expanding removes
 * that class. A hidden copy *and* a visible copy would announce every figure
 * twice.
 */
export function ChartDataTable({
  chart,
  caption,
  visible,
  className,
}: {
  chart: NormalisedChart;
  caption: string;
  visible: boolean;
  className?: string;
}) {
  if (chart.isEmpty) return null;

  return (
    <div className={cn(visible ? "overflow-x-auto" : "sr-only", className)}>
      <table className="w-full border-collapse text-sm">
        <caption className="text-muted-foreground mb-2 text-left text-xs">{caption}</caption>
        <thead>
          <tr className="border-b">
            <th scope="col" className="text-muted-foreground py-2 pr-4 text-left font-medium">
              {chart.xAxisLabel ?? "Category"}
            </th>
            {chart.series.map((series) => (
              <th
                key={series.label}
                scope="col"
                className="text-muted-foreground py-2 pr-4 text-right font-medium tabular-nums"
              >
                {series.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {chart.labels.map((label, row) => (
            <tr key={label} className="border-border/60 border-b last:border-0">
              <th scope="row" className="py-2 pr-4 text-left font-normal">
                {label}
              </th>
              {chart.series.map((series) => (
                <td key={series.label} className="py-2 pr-4 text-right font-medium tabular-nums">
                  {formatValue(series.data[row] ?? null, chart.unit)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
