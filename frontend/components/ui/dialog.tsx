"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * A modal, used only where one is warranted.
 *
 * Sprint 12 chose a *banner* for the level-up moment precisely because a
 * dialog steals focus and dismisses itself. What is left for a dialog is the
 * opposite case: an action that must not proceed by accident — deactivating a
 * vocabulary term, changing someone's role — where taking focus and demanding
 * a decision is the point.
 *
 * Radix supplies the parts that are hard to get right and invisible when they
 * are wrong: the focus trap, focus restored to whatever opened it, `Escape`,
 * the inert background, and the `aria-labelledby`/`describedby` wiring. Every
 * `DialogContent` therefore *must* contain a `DialogTitle`; Radix warns in
 * development when it does not.
 */
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay
        // No enter animation: `animate-in` belongs to a plugin this project
        // does not load, and a dialog that appears instantly is the correct
        // behaviour under `prefers-reduced-motion` anyway.
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-[2px]"
      />
      <DialogPrimitive.Content
        className={cn(
          "bg-card text-card-foreground fixed z-50 flex flex-col gap-4 border shadow-lg",
          // A sheet from the bottom on a phone — reachable with the thumb that
          // is already holding it — and a centred card once there is room.
          "inset-x-0 bottom-0 max-h-[90dvh] overflow-y-auto rounded-t-xl p-6",
          "sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl",
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          className={cn(
            "text-muted-foreground hover:text-foreground focus-visible:ring-ring absolute top-4 right-4",
            "rounded-md p-1 transition-colors focus-visible:ring-2 focus-visible:outline-none",
          )}
        >
          <X className="size-4" aria-hidden />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("flex flex-col gap-1.5 pr-8", className)} {...props} />;
}

export function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      className={cn("text-lg font-semibold tracking-tight", className)}
      {...props}
    />
  );
}

export function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      className={cn("text-muted-foreground text-sm text-pretty", className)}
      {...props}
    />
  );
}

/** Actions, reversed on a phone so the confirming one sits under the thumb. */
export function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end", className)}
      {...props}
    />
  );
}
