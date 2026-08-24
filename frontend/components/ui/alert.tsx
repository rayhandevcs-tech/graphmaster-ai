import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-lg border p-4 text-sm [&>svg]:absolute [&>svg]:top-4 [&>svg]:left-4 " +
    "[&>svg]:size-4 [&>svg~*]:pl-7",
  {
    variants: {
      variant: {
        default: "bg-card text-card-foreground",
        info: "border-secondary/40 bg-secondary/10 text-foreground",
        success: "border-success/40 bg-success/10 text-foreground",
        warning: "border-tier-hammer/50 bg-tier-hammer/10 text-foreground",
        destructive: "border-destructive/50 bg-destructive/10 text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface AlertProps
  extends React.ComponentPropsWithoutRef<"div">, VariantProps<typeof alertVariants> {}

/**
 * `role` follows the variant: an error a student needs to act on is announced,
 * an informational note is not. Both are readable without the colour, which is
 * why the title text carries the meaning (NFR-4.6).
 */
export function Alert({ className, variant, ...props }: AlertProps) {
  return (
    <div
      role={variant === "destructive" ? "alert" : "status"}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  );
}

export function AlertTitle({ className, ...props }: React.ComponentPropsWithoutRef<"h5">) {
  return (
    <h5 className={cn("mb-1 leading-none font-medium tracking-tight", className)} {...props} />
  );
}

export function AlertDescription({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return <div className={cn("text-muted-foreground text-sm", className)} {...props} />;
}
