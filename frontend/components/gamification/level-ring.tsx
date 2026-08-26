import { cn } from "@/lib/utils";

/**
 * The level, with progress through it drawn around the number.
 *
 * One of the three places gold is allowed (06-frontend-architecture §4): the
 * crown tier, the XP bar and the level-up moment are what the colour means,
 * and this ring is the XP bar's compact form.
 *
 * It carries `aria-hidden` and no text of its own. The same numbers are
 * announced by the XP bar beside it, which is a real `progressbar` with a
 * label; a second, differently worded copy of "level 4, 60% of the way to 5"
 * is noise in a screen reader, not redundancy.
 */
const SIZE = 96;
const STROKE = 8;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function LevelRing({
  level,
  progressPercent,
  isMaxLevel,
  className,
}: {
  level: number;
  progressPercent: number;
  isMaxLevel: boolean;
  className?: string;
}) {
  // A full ring at the cap: there is no next level to fill towards, and a ring
  // frozen part-way reads as progress that stalled.
  const fraction = isMaxLevel ? 1 : Math.min(Math.max(progressPercent, 0), 100) / 100;

  return (
    <div className={cn("relative shrink-0", className)} aria-hidden>
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="size-24 -rotate-90">
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          strokeWidth={STROKE}
          className="stroke-gold/20"
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - fraction)}
          className="stroke-gold transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>

      <span className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-muted-foreground text-[0.625rem] font-medium tracking-widest uppercase">
          Level
        </span>
        <span className="text-2xl leading-none font-semibold tabular-nums">{level}</span>
      </span>
    </div>
  );
}
