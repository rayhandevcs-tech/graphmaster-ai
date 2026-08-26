"use client";

import Link from "next/link";
import { ArrowRight, PenLine, Sparkles, Table2 } from "lucide-react";

import { useRubric, weightingSentence, wordBandLabel } from "@/lib/hooks/use-rubric";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/**
 * The dashboard before there is anything to show on it.
 *
 * A student with no marked work would otherwise meet four em dashes, an empty
 * chart and two empty lists — a screen that looks broken and says nothing
 * about what to do. This replaces the whole record-of-work half of the
 * dashboard with an explanation of the loop and one way into it.
 *
 * The marking criteria come from `GET /analysis/rubric`, not from this file.
 * They are configuration, and a hardcoded "70%" here would go on being shown
 * after a deployment retuned the weights. If the request fails the sentence is
 * simply absent — the three steps are the point, and none of them depend on it.
 */
const STEPS = [
  {
    icon: Table2,
    title: "Pick a graph",
    body: "Line, bar, pie or area — each one comes with the task and a data table you can read the figures from.",
  },
  {
    icon: PenLine,
    title: "Describe what it shows",
    body: "Type it, or photograph a handwritten answer and check the text we read back before it is marked.",
  },
  {
    icon: Sparkles,
    title: "See what you used",
    body: "Every target word you reached for is highlighted in your own writing, with the ones you missed named.",
  },
];

export function FirstRun() {
  const { data: rubric } = useRubric();
  const weighting = weightingSentence(rubric);
  const band = wordBandLabel(rubric);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold tracking-tight">How practice works</h2>
        <p className="text-muted-foreground max-w-2xl text-sm text-pretty">
          {weighting ?? "Your description is marked on the academic vocabulary it uses."}{" "}
          {band ? `Aim for ${band}.` : null}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {STEPS.map((step, index) => (
          <Card key={step.title} className="flex flex-col gap-3 p-5">
            <div className="flex items-center gap-3">
              <span className="bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg">
                <step.icon className="size-4" aria-hidden />
              </span>
              {/* The number is real information here: these happen in order. */}
              <span className="text-muted-foreground text-xs font-medium tracking-widest tabular-nums">
                STEP {index + 1}
              </span>
            </div>
            <h3 className="font-semibold tracking-tight">{step.title}</h3>
            <p className="text-muted-foreground text-sm text-pretty">{step.body}</p>
          </Card>
        ))}
      </div>

      <Button asChild size="lg" className="w-full sm:w-fit">
        <Link href="/practice">
          Choose your first graph
          <ArrowRight aria-hidden />
        </Link>
      </Button>
    </div>
  );
}
