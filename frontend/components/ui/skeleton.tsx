import { cn } from "@/lib/utils";

/**
 * `aria-hidden` on purpose: the placeholder means nothing read aloud, and the
 * region it fills carries its own `aria-busy`.
 */
export function Skeleton({ className, ...props }: React.ComponentPropsWithoutRef<"div">) {
  return (
    <div aria-hidden className={cn("bg-muted animate-pulse rounded-md", className)} {...props} />
  );
}
