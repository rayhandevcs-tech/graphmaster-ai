"use client";

import * as React from "react";
import * as AvatarPrimitive from "@radix-ui/react-avatar";

import { cn } from "@/lib/utils";

/**
 * A circle with a person's initials in it.
 *
 * **There is deliberately no `AvatarImage`.** The avatar catalogue's
 * `image_url` points at six SVGs that have never existed in this repository,
 * so every use of an image avatar rendered a 404 and fell back to letters.
 * A student's chosen character is drawn by `components/avatars/character.tsx`;
 * this is for the places where there is no character to draw — a teacher's
 * roster, an administrator's user list — where a name is all there is.
 */

export const Avatar = React.forwardRef<
  React.ComponentRef<typeof AvatarPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root>
>(function Avatar({ className, ...props }, ref) {
  return (
    <AvatarPrimitive.Root
      ref={ref}
      className={cn("relative flex size-10 shrink-0 overflow-hidden rounded-full", className)}
      {...props}
    />
  );
});

export const AvatarFallback = React.forwardRef<
  React.ComponentRef<typeof AvatarPrimitive.Fallback>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback>
>(function AvatarFallback({ className, ...props }, ref) {
  return (
    <AvatarPrimitive.Fallback
      ref={ref}
      className={cn(
        "bg-muted text-muted-foreground flex size-full items-center justify-center rounded-full text-sm font-medium",
        className,
      )}
      {...props}
    />
  );
});
