import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Nothing here, and why.
 *
 * An empty grid with no explanation reads as a page that failed to load. Every
 * empty state in the student flow names the cause and offers the one action
 * that resolves it — a filter to clear, a first graph to try.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  title: string;
  description: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "border-border/70 flex flex-col items-center justify-center gap-3 rounded-xl",
        "border border-dashed px-6 py-16 text-center",
        className,
      )}
    >
      <span className="bg-muted text-muted-foreground flex size-11 items-center justify-center rounded-full">
        <Icon className="size-5" aria-hidden />
      </span>
      <h3 className="text-base font-semibold tracking-tight">{title}</h3>
      <p className="text-muted-foreground max-w-sm text-sm text-pretty">{description}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
