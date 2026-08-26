import { cn } from "@/lib/utils";

/**
 * A pill-shaped toggle, and the only one in the product.
 *
 * There were two. `FilterChips` shipped in Sprint 11 at `py-1.5 text-xs` —
 * about 30px — and the leaderboard's scope row shipped in Sprint 13 with a
 * `min-h-11` floor. Same shape, same behaviour, two different answers to
 * whether a thumb can hit it. The 30px one was the filter control on five
 * screens.
 *
 * The floor is 44px until `sm:`, matching `Button`: a pointer is the likely
 * input at that width and the extra height only costs vertical rhythm, while
 * below it every chip is a touch target.
 *
 * `aria-pressed` rather than `role="tab"` — these filter a list that is already
 * on the page; they do not switch panels.
 */
export function Chip({
  pressed,
  onPress,
  children,
  className,
}: {
  pressed: boolean;
  onPress: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onPress}
      className={cn(
        "focus-visible:ring-ring inline-flex min-h-11 items-center rounded-full border px-3.5 text-sm",
        "font-medium transition-colors focus-visible:ring-2 focus-visible:ring-offset-2",
        "focus-visible:outline-none sm:min-h-8 sm:px-3 sm:text-xs",
        pressed
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border text-muted-foreground hover:border-input hover:text-foreground",
        className,
      )}
    >
      {children}
    </button>
  );
}
