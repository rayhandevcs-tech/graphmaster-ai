import { formatShortDate } from "@/lib/format";
import type { ChartData, app__schemas__analytics__TrendPoint } from "@/types/api";

/**
 * One day of marked work.
 *
 * Aliased because two different schemas are named `TrendPoint` in the API — the
 * analytics one used here, and the assessment one — so the generator qualifies
 * both with their module path. The qualified name is unreadable at a call site
 * and says nothing a reader needs; this is the only place it appears.
 */
export type ScoreTrendPoint = app__schemas__analytics__TrendPoint;

/**
 * The score trend as something the existing chart layer can draw.
 *
 * The dashboard's trend is not a graph a teacher authored, but it is the same
 * *shape* — labels and named series — so it is handed to `ChartPanel` as
 * synthetic `chart_data` rather than growing a second charting component. The
 * theming, the lazy Chart.js import, the data-table alternative and the
 * screen-reader description then all apply to it unchanged.
 *
 * **The x-axis is practice days, not a calendar.** The API returns one bucket
 * per day the student actually submitted, with no zero-filled gaps — so two
 * adjacent points can be a day or a month apart. Spacing them evenly is a
 * deliberate choice: this answers "is my work improving", where the ordering
 * is the information and the interval is not. Interpolating across the gaps
 * would draw a line through days that never happened, and the surface says so
 * in words beside the chart rather than leaving the reader to assume a
 * calendar.
 */
export function trendChartData(points: ScoreTrendPoint[]): ChartData {
  return {
    labels: points.map((point) => formatShortDate(point.date)),
    datasets: [
      {
        label: "Overall score",
        data: points.map((point) => point.average_final_score),
      },
      {
        label: "Vocabulary",
        data: points.map((point) => point.average_vocabulary_percentage),
      },
    ],
    x_axis_label: "Days you practised",
    y_axis_label: "Percentage",
    unit: "%",
  };
}
