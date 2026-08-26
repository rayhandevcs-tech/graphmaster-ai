"use client";

import { m } from "framer-motion";
import { ArrowUp, Sparkles } from "lucide-react";

import { MotionStage } from "@/components/motion/stage";
import { CountUp } from "@/components/motion/count-up";
import { Sparkles as SparkleBurst } from "./particles";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";
import { SPRING } from "@/lib/motion/tokens";
import { cn } from "@/lib/utils";

/**
 * Reaching a new level.
 *
 * A **banner, not a modal**. A dialog over a result steals focus from the
 * thing the student came to read and has to be dismissed before the feedback
 * can be seen — and the moment it celebrates is a side effect of work already
 * displayed on the same screen. It arrives above the award summary, announces
 * itself once, and stays: a self-dismissing celebration is missed by exactly
 * the student who looked away, which is the failure mode nobody notices in
 * review because reviewers are watching.
 *
 * Gold is right here. This is one of the three surfaces the palette reserves
 * it for — the crown, the XP bar, and this (06-frontend-architecture §4).
 */
export function LevelUpBanner({
  from,
  to,
  className,
}: {
  from: number;
  to: number;
  className?: string;
}) {
  const reducedMotion = useReducedMotion();

  return (
    <MotionStage>
      <m.div
        // `role="status"` rather than `alert`: reaching a level is good news,
        // not something to interrupt a screen reader mid-sentence for.
        role="status"
        className={cn(
          "border-gold/40 from-gold/15 relative flex items-center gap-4 overflow-hidden",
          "rounded-xl border bg-gradient-to-r to-transparent p-4",
          className,
        )}
        initial={reducedMotion ? false : { opacity: 0, y: -8, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={SPRING}
      >
        {reducedMotion ? null : <SparkleBurst count={5} />}

        <span className="bg-gold text-gold-foreground relative flex size-11 shrink-0 items-center justify-center rounded-full">
          <ArrowUp className="size-5" aria-hidden />
        </span>

        <div className="relative flex flex-col">
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
            <Sparkles className="text-gold size-3.5" aria-hidden />
            Level up
          </span>
          <span className="text-muted-foreground text-sm">
            You have reached{" "}
            <span className="text-foreground font-semibold tabular-nums">
              level <CountUp value={to} format={(value) => String(Math.round(value))} />
            </span>
            {from < to ? <span className="tabular-nums"> — up from {from}</span> : null}
          </span>
        </div>
      </m.div>
    </MotionStage>
  );
}
