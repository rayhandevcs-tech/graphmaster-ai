"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Collapsible on a phone, always open on a desktop.
 *
 * The practice page is the hard case for NFR-4.1: on a narrow screen the chart
 * sits directly above the textarea, so without this a student scrolls past the
 * whole graph to get back to what they were writing. Above `lg` the two are
 * side by side and there is nothing to collapse, so the control itself
 * disappears rather than becoming a toggle with no purpose.
 */
export function CollapsiblePanel({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(true);
  const regionId = useId();

  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-controls={regionId}
        className={cn(
          "text-muted-foreground hover:text-foreground focus-visible:ring-ring flex w-full",
          "items-center justify-between gap-2 rounded-md px-1 py-2 text-xs font-medium",
          "tracking-wide uppercase transition-colors focus-visible:ring-2 focus-visible:outline-none",
          "lg:hidden",
        )}
      >
        {title}
        <ChevronDown
          className={cn("size-4 transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>

      <div id={regionId} className={cn(open ? "block" : "hidden", "lg:block")}>
        {children}
      </div>
    </div>
  );
}
