import * as React from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * A native `<select>`, deliberately.
 *
 * A custom listbox is the shadcn default and it is the wrong call here. On a
 * phone the native control opens the platform's own picker — a thumb-sized
 * wheel or sheet, scrollable with one hand, with the system's own search and
 * accessibility behaviour already correct. Reimplementing that costs a
 * dependency, a focus-management surface to get wrong, and a worse result on
 * exactly the device this product is used on.
 *
 * What the platform does *not* style is the arrow, so `appearance-none` plus
 * one icon is the whole customisation.
 */
export const Select = React.forwardRef<HTMLSelectElement, React.ComponentProps<"select">>(
  function Select({ className, children, ...props }, ref) {
    return (
      <div className="relative inline-flex w-full">
        <select
          ref={ref}
          className={cn(
            "border-input bg-background ring-offset-background h-11 w-full appearance-none rounded-md border",
            "py-2 pr-9 pl-3 text-sm transition-colors sm:h-10",
            "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
            "disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
          {...props}
        >
          {children}
        </select>
        <ChevronDown
          className="text-muted-foreground pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2"
          aria-hidden
        />
      </div>
    );
  },
);
