import * as React from "react";

import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.ComponentPropsWithoutRef<"input">>(
  function Input({ className, type = "text", ...props }, ref) {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          "border-input bg-background ring-offset-background placeholder:text-muted-foreground",
          "focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm",
          "focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
          "disabled:cursor-not-allowed disabled:opacity-50",
          // `aria-invalid` rather than a prop: the attribute is what a screen
          // reader announces, so styling from it keeps the two in step.
          "aria-[invalid=true]:border-destructive aria-[invalid=true]:focus-visible:ring-destructive",
          className,
        )}
        {...props}
      />
    );
  },
);
