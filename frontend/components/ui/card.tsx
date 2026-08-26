import * as React from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return (
    <div
      className={cn("bg-card text-card-foreground rounded-xl border shadow-sm", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return <div className={cn("flex flex-col gap-1.5 p-6", className)} {...props} />;
}

/**
 * A card's heading, at the level the *page* needs.
 *
 * Defaults to `h3`, which is right for a card inside a page that already has
 * an `h1`. The sign-in and registration screens are a card *and* the whole
 * page, so their title is the document's `h1` — without `as`, those pages had
 * no top-level heading at all and a screen-reader user navigating by heading
 * found nothing (WCAG 1.3.1, 2.4.6).
 */
export function CardTitle({
  as: Component = "h3",
  className,
  ...props
}: React.ComponentPropsWithoutRef<"h3"> & { as?: "h1" | "h2" | "h3" }) {
  return (
    <Component
      className={cn("text-lg leading-none font-semibold tracking-tight", className)}
      {...props}
    />
  );
}

export function CardDescription({ className, ...props }: React.ComponentPropsWithoutRef<"p">) {
  return <p className={cn("text-muted-foreground text-sm", className)} {...props} />;
}

export function CardContent({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return <div className={cn("p-6 pt-0", className)} {...props} />;
}

export function CardFooter({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return <div className={cn("flex items-center p-6 pt-0", className)} {...props} />;
}
