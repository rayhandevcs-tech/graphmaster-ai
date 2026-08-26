import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A table, for the width where a table is the right answer.
 *
 * Dense staff data gets two presentations rather than one responsive
 * compromise: a list of cards below `md`, and this at `md` and above. A table
 * squeezed onto a 390px screen is the horizontal scroll the design directive
 * rules out, and a stack of cards on a wide monitor throws away the
 * column-to-column comparison a teacher opened the screen to make.
 *
 * The wrapper still scrolls horizontally as a last resort — a long class name
 * or a wide date should scroll *inside the table*, never take the page with
 * it.
 */
export function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn("w-full caption-bottom text-sm", className)} {...props} />
    </div>
  );
}

export function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return <thead className={cn("[&_tr]:border-b", className)} {...props} />;
}

export function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}

export function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      className={cn("border-border hover:bg-muted/40 border-b transition-colors", className)}
      {...props}
    />
  );
}

export function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      className={cn(
        "text-muted-foreground h-10 px-3 text-left align-middle text-xs font-medium tracking-wide uppercase",
        "[&:has([role=checkbox])]:pr-0",
        className,
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return <td className={cn("px-3 py-3 align-middle", className)} {...props} />;
}

/** Below the table, where a screen reader reaches it after the data. */
export function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return <caption className={cn("text-muted-foreground mt-3 text-xs", className)} {...props} />;
}
