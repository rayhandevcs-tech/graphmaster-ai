"use client";

import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils";

/**
 * Radix underneath, so the roving tab index, the arrow keys and the
 * `aria-controls` wiring are the library's problem rather than ours. The
 * practice page depends on that: switching between typing and handwriting has
 * to be reachable without a mouse.
 */
export const Tabs = TabsPrimitive.Root;

export const TabsList = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(function TabsList({ className, ...props }, ref) {
  return (
    <TabsPrimitive.List
      ref={ref}
      className={cn(
        "bg-muted text-muted-foreground inline-flex h-10 items-center justify-center rounded-lg p-1",
        className,
      )}
      {...props}
    />
  );
});

export const TabsTrigger = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(function TabsTrigger({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(
        "ring-offset-background focus-visible:ring-ring inline-flex items-center justify-center",
        "gap-2 rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-all",
        "focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
        "disabled:pointer-events-none disabled:opacity-50",
        "data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm",
        "[&_svg]:size-4 [&_svg]:shrink-0",
        className,
      )}
      {...props}
    />
  );
});

export const TabsContent = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(function TabsContent({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Content
      ref={ref}
      className={cn(
        "ring-offset-background focus-visible:ring-ring mt-4 focus-visible:ring-2",
        "focus-visible:ring-offset-2 focus-visible:outline-none",
        className,
      )}
      {...props}
    />
  );
});
