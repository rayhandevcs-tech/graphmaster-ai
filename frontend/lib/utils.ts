import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names, letting a caller's class win over a component's default.
 *
 * `clsx` flattens conditionals; `tailwind-merge` resolves the conflicts it
 * leaves behind, so `cn("p-2", "p-4")` is `p-4` rather than both — which in
 * plain CSS would be decided by stylesheet order and look like a bug.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
