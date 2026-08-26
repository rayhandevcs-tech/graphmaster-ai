import Link from "next/link";
import { Highlighter, LineChart, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The frame around signing in and signing up.
 *
 * Two columns on a large screen, one on a phone — and the form comes first in
 * the document either way. The panel beside it is the reason to create an
 * account, and a screen-reader user should reach the fields before the sales
 * pitch, not after it.
 *
 * The panel is `aria-hidden` on top of being hidden below `lg`: everything in
 * it also appears in the marketing page these pages link back to, and the
 * three claims below are decoration on the form, not information a student
 * needs in order to sign in.
 */
const PROMISES = [
  {
    icon: LineChart,
    title: "Real charts, not screenshots",
    body: "Every graph is live data you can read the figures from, on any screen size.",
  },
  {
    icon: Highlighter,
    title: "See the words you used",
    body: "Your own writing comes back with each target term highlighted where you wrote it.",
  },
  {
    icon: Sparkles,
    title: "Marked in seconds",
    body: "Type it or photograph it. The reading is yours to correct before anything is marked.",
  },
];

export function AuthShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mx-auto grid w-full max-w-5xl items-center gap-12 py-4 lg:grid-cols-[minmax(0,26rem)_1fr] lg:gap-20",
        className,
      )}
    >
      <div className="w-full">{children}</div>

      <aside className="hidden flex-col gap-8 lg:flex" aria-hidden>
        <div className="flex flex-col gap-3">
          <span className="text-primary text-xs font-semibold tracking-widest uppercase">
            GraphMaster
          </span>
          <p className="max-w-sm text-2xl leading-snug font-semibold tracking-tight text-balance">
            Describe a graph in academic English, and find out which words earned the marks.
          </p>
        </div>

        <ChartMotif />

        <ul className="flex flex-col gap-5">
          {PROMISES.map((promise) => (
            <li key={promise.title} className="flex gap-3">
              <span className="bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg">
                <promise.icon className="size-4" />
              </span>
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-semibold">{promise.title}</span>
                <span className="text-muted-foreground max-w-sm text-sm text-pretty">
                  {promise.body}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

/**
 * A bar chart drawn in CSS.
 *
 * Not a Chart.js instance: this is ornament on a page whose job is a form, and
 * loading a charting library to draw six rectangles that carry no data would
 * put a download in front of the sign-in button. The heights are arbitrary and
 * mean nothing, which is exactly why it must never look like a real reading —
 * it has no axis, no labels and no numbers.
 */
const MOTIF_HEIGHTS = ["h-10", "h-16", "h-12", "h-24", "h-20", "h-28"];

function ChartMotif() {
  return (
    <div className="bg-card/60 flex h-40 items-end gap-2 rounded-xl border p-4">
      {MOTIF_HEIGHTS.map((height, index) => (
        <span
          key={height + index}
          className={cn(
            "flex-1 rounded-t-md",
            height,
            index % 2 === 0 ? "bg-primary/25" : "bg-secondary/30",
          )}
        />
      ))}
    </div>
  );
}

/** The line under an auth card: the other way in. */
export function AuthSwitch({
  prompt,
  href,
  label,
}: {
  prompt: string;
  href: string;
  label: string;
}) {
  return (
    <p className="text-muted-foreground text-center text-sm">
      {prompt}{" "}
      <Link href={href} className="text-primary font-medium underline-offset-4 hover:underline">
        {label}
      </Link>
    </p>
  );
}
