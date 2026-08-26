import { ArrowLeft, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Previous / next over a `Page<T>`.
 *
 * Numbered pages are not worth it here: the API is offset-paginated and a
 * student browsing a library reads forwards. The counts are shown because
 * "Page 2" on its own does not say whether there is a page 3.
 */
export function Pager({
  page,
  totalPages,
  total,
  onPageChange,
  itemNoun = "graphs",
}: {
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (next: number) => void;
  itemNoun?: string;
}) {
  if (totalPages <= 1) return null;

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-4 border-t pt-6"
    >
      <p className="text-muted-foreground text-sm" aria-live="polite">
        Page {page} of {totalPages} · {total.toLocaleString()} {itemNoun}
      </p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ArrowLeft aria-hidden />
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
          <ArrowRight aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
