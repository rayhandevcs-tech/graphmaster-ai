import { splitAnswer } from "@/lib/results/highlight";
import { cn } from "@/lib/utils";
import type { DetectedTermOut } from "@/types/api";

/**
 * The answer as the student wrote it, with the target vocabulary marked.
 *
 * The highlight is a *visual* aid and is treated as one. A screen-reader user
 * gets the answer as continuous prose — annotating two hundred words inline
 * would make it unreadable — and the same information as a list of terms
 * beneath it, which is the representation that actually teaches.
 *
 * `<mark>` carries the highlighting semantics natively, so no ARIA is invented
 * here. Required and optional terms differ in tone *and* in the legend, never
 * in colour alone (NFR-4.6).
 */
export function HighlightedAnswer({
  text,
  terms,
  className,
}: {
  text: string;
  terms: readonly DetectedTermOut[];
  className?: string;
}) {
  const segments = splitAnswer(text, terms);
  const hasOptional = terms.some((term) => !term.is_required);

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
        <span className="inline-flex items-center gap-1.5">
          <span className="bg-primary/20 border-primary/40 size-3 rounded-sm border" aria-hidden />
          Required target term
        </span>
        {hasOptional ? (
          <span className="inline-flex items-center gap-1.5">
            <span
              className="bg-secondary/20 border-secondary/40 size-3 rounded-sm border"
              aria-hidden
            />
            Optional term
          </span>
        ) : null}
      </div>

      <p className="text-[0.95rem] leading-7 whitespace-pre-wrap">
        {segments.map((segment, index) =>
          segment.term ? (
            <mark
              key={index}
              className={cn(
                "rounded-sm px-0.5 py-px text-inherit",
                segment.term.is_required
                  ? "bg-primary/20 decoration-primary/50"
                  : "bg-secondary/20 decoration-secondary/50",
              )}
            >
              {segment.text}
            </mark>
          ) : (
            <span key={index}>{segment.text}</span>
          ),
        )}
      </p>
    </div>
  );
}
