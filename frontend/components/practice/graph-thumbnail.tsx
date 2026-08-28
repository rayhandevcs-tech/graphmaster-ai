import { cn } from "@/lib/utils";
import type { GraphPreview, GraphType } from "@/types/api";

/**
 * The shape of a graph, at card size.
 *
 * **Not a Chart.js instance.** A library page shows twenty of these, and
 * twenty canvases with twenty animation loops is a scroll that stutters on the
 * phones this is used on. It is also the wrong drawing: at 200px wide no axis
 * label, tick or legend is legible, so a faithful miniature spends its whole
 * budget on furniture nobody can read.
 *
 * What survives at this size is the *shape* — rising, falling, spiky, one
 * slice dominating — which is exactly what a student is choosing between. So
 * the API sends the series values alone (`GraphPreview`) and this draws a few
 * paths from them.
 *
 * **Baselines differ by type, and it matters.** Bars and areas are measured
 * from zero, because a bar drawn from its own series minimum turns a rise from
 * 98 to 100 into a full-height column and lies about the data. A line is drawn
 * across its own range, because a line pinned to zero flattens the shape it
 * exists to show. This is the same split Chart.js makes by default, for the
 * same reason.
 *
 * Gaps are gaps. A null breaks the line rather than being interpolated over,
 * which is the honest drawing and matches how the full chart renders it.
 */

const WIDTH = 120;
const HEIGHT = 64;
const PAD = 8;

/** Written out because Tailwind scans source text for whole class names. */
const STROKE = ["stroke-chart-1", "stroke-chart-2", "stroke-chart-3"] as const;
const FILL = ["fill-chart-1", "fill-chart-2", "fill-chart-3"] as const;
const SLICES = [
  "fill-chart-1",
  "fill-chart-2",
  "fill-chart-3",
  "fill-chart-4",
  "fill-chart-5",
  "fill-chart-6",
] as const;

export function GraphThumbnail({
  graphType,
  preview,
  className,
}: {
  graphType: GraphType;
  preview: GraphPreview | null | undefined;
  className?: string;
}) {
  // At most three series. A fourth line at this size is noise, and the card is
  // a way in rather than a reading of the data.
  const series = (preview?.series ?? []).slice(0, 3).filter((points) => points.length > 0);
  const numbers = series.flat().filter((value): value is number => typeof value === "number");

  if (series.length === 0 || numbers.length === 0) return <EmptyThumbnail className={className} />;

  // A pie is the one type that must not be stretched. The others *should*
  // fill the card — a line graph is a shape over a span and squashing it
  // changes nothing a reader would object to — but a squashed circle is
  // simply a different chart, and the card's box is not a fixed ratio once a
  // phone narrows it. So the pie is drawn in a square frame that scales to
  // fit, and the rest keep `none`.
  if (graphType === "pie") {
    return (
      <svg
        viewBox={`0 0 ${HEIGHT} ${HEIGHT}`}
        className={cn("h-full w-full", className)}
        preserveAspectRatio="xMidYMid meet"
        aria-hidden
      >
        <Pie points={series[0] as (number | null)[]} />
      </svg>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className={cn("h-full w-full", className)}
      preserveAspectRatio="none"
      aria-hidden
    >
      {graphType === "bar" ? (
        <Bars series={series} />
      ) : (
        <Lines series={series} filled={graphType === "area"} />
      )}
    </svg>
  );
}

/**
 * A graph whose figures could not be read.
 *
 * Drawn rather than left blank: an empty box in a grid of pictures reads as a
 * card that has not finished loading, and a student waits for it.
 */
function EmptyThumbnail({ className }: { className?: string }) {
  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className={cn("h-full w-full", className)}
      preserveAspectRatio="none"
      aria-hidden
    >
      <g className="stroke-border" strokeWidth="2" strokeLinecap="round">
        <path d={`M${PAD} ${HEIGHT - PAD}h${WIDTH - PAD * 2}`} />
        <path d={`M${PAD} ${PAD}v${HEIGHT - PAD * 2}`} />
      </g>
    </svg>
  );
}

/** The value range a series is drawn across. */
function range(numbers: number[], fromZero: boolean) {
  let min = Math.min(...numbers);
  let max = Math.max(...numbers);
  if (fromZero) min = Math.min(min, 0);
  if (max === min) {
    // A flat series still has to occupy the box rather than collapsing onto
    // one edge, and dividing by zero would put every point at NaN.
    max = min + 1;
  }
  return { min, max };
}

const xAt = (index: number, count: number) =>
  count === 1 ? WIDTH / 2 : PAD + (index * (WIDTH - PAD * 2)) / (count - 1);

function Lines({ series, filled }: { series: (number | null)[][]; filled: boolean }) {
  const numbers = series.flat().filter((value): value is number => typeof value === "number");
  const { min, max } = range(numbers, filled);
  const yAt = (value: number) => HEIGHT - PAD - ((value - min) / (max - min)) * (HEIGHT - PAD * 2);

  return (
    <>
      {series.map((points, index) => {
        // Split on nulls, so a gap breaks the line instead of being drawn
        // across. Each run becomes its own path.
        const runs: { x: number; y: number }[][] = [];
        let run: { x: number; y: number }[] = [];
        points.forEach((value, i) => {
          if (typeof value === "number") {
            run.push({ x: xAt(i, points.length), y: yAt(value) });
          } else if (run.length) {
            runs.push(run);
            run = [];
          }
        });
        if (run.length) runs.push(run);

        return (
          <g key={index}>
            {filled
              ? runs.map((segment, r) => (
                  <path
                    key={`f${r}`}
                    d={
                      `M${segment[0]?.x} ${HEIGHT - PAD}` +
                      segment.map((p) => `L${p.x} ${p.y}`).join("") +
                      `L${segment[segment.length - 1]?.x} ${HEIGHT - PAD}Z`
                    }
                    className={FILL[index % FILL.length]}
                    opacity="0.28"
                  />
                ))
              : null}
            {runs.map((segment, r) => (
              <path
                key={`l${r}`}
                d={segment.map((p, i) => `${i === 0 ? "M" : "L"}${p.x} ${p.y}`).join("")}
                className={cn(STROKE[index % STROKE.length], "fill-none")}
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                // The box is stretched to the card, so an untouched stroke
                // would be thicker vertically than horizontally.
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </g>
        );
      })}
    </>
  );
}

function Bars({ series }: { series: (number | null)[][] }) {
  const numbers = series.flat().filter((value): value is number => typeof value === "number");
  const { min, max } = range(numbers, true);
  const count = Math.max(...series.map((points) => points.length));
  const band = (WIDTH - PAD * 2) / count;
  const gap = Math.min(2, band * 0.18);
  const barWidth = Math.max(1.5, (band - gap) / series.length);
  const zero = HEIGHT - PAD - ((0 - min) / (max - min)) * (HEIGHT - PAD * 2);

  return (
    <>
      {series.map((points, s) =>
        points.map((value, i) => {
          if (typeof value !== "number") return null;
          const y = HEIGHT - PAD - ((value - min) / (max - min)) * (HEIGHT - PAD * 2);
          const top = Math.min(y, zero);
          return (
            <rect
              key={`${s}-${i}`}
              x={PAD + i * band + gap / 2 + s * barWidth}
              y={top}
              width={barWidth}
              // A bar for a value equal to the baseline still has to be
              // visible, or a zero reads as missing data.
              height={Math.max(1, Math.abs(zero - y))}
              className={FILL[s % FILL.length]}
              opacity={s === 0 ? 0.9 : 0.65}
            />
          );
        }),
      )}
    </>
  );
}

function Pie({ points }: { points: (number | null)[] }) {
  // Negative slices are not a pie. Anything that is not a positive number is
  // dropped rather than drawn as a wedge going the wrong way round.
  const values = points.filter((value): value is number => typeof value === "number" && value > 0);
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total <= 0) return null;

  const c = HEIGHT / 2;
  const r = c - PAD / 2;
  let angle = -Math.PI / 2;

  return (
    <>
      {values.map((value, index) => {
        const sweep = (value / total) * Math.PI * 2;
        const from = angle;
        angle += sweep;

        const x1 = c + r * Math.cos(from);
        const y1 = c + r * Math.sin(from);
        const x2 = c + r * Math.cos(angle);
        const y2 = c + r * Math.sin(angle);
        const large = sweep > Math.PI ? 1 : 0;

        // One slice makes a whole circle, and an arc from a point back to
        // itself draws nothing at all.
        const d =
          values.length === 1
            ? `M${c - r} ${c}a${r} ${r} 0 1 0 ${r * 2} 0a${r} ${r} 0 1 0 ${-r * 2} 0z`
            : `M${c} ${c}L${x1} ${y1}A${r} ${r} 0 ${large} 1 ${x2} ${y2}Z`;

        return <path key={index} d={d} className={SLICES[index % SLICES.length]} />;
      })}
    </>
  );
}
