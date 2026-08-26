"use client";

import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { RANGE_OPTIONS } from "@/lib/insights/scope";
import type { ClassScope } from "@/lib/hooks/use-class-scope";
import { cn } from "@/lib/utils";

/**
 * Which class, over what period — on every teaching screen, in the same place.
 *
 * Sticky beneath the site header, because a teacher halfway down a roster who
 * has forgotten which class they are reading should not have to scroll back to
 * find out. `top-16` is the header's own height; a focused row underneath gets
 * `scroll-margin-top` from the pages so the browser never parks it out of
 * sight behind this bar.
 *
 * `summary` is the screen's headline figures in words — "18 of 31 students,
 * 214 marked attempts". It is rendered visibly *and* announced politely,
 * because changing a filter otherwise gives a keyboard or screen-reader user
 * no feedback at all: the numbers move somewhere they cannot see.
 */
export function ScopeBar({
  scope,
  summary,
  actions,
  className,
}: {
  scope: ClassScope;
  summary?: string;
  /** Export, or whatever this screen offers on the same line. */
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-16 z-30",
        "-mx-4 mb-2 border-b px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6",
        className,
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          {scope.isEmpty ? null : (
            <div className="flex min-w-0 flex-col gap-1 sm:w-56">
              <Label htmlFor="scope-class" className="text-muted-foreground text-xs">
                Class
              </Label>
              <Select
                id="scope-class"
                value={scope.classId ?? ""}
                disabled={scope.isLoading}
                onChange={(event) => scope.setClassId(event.target.value || null)}
              >
                {scope.classes.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div className="flex flex-col gap-1 sm:w-44">
            <Label htmlFor="scope-range" className="text-muted-foreground text-xs">
              Period
            </Label>
            <Select
              id="scope-range"
              value={scope.range}
              onChange={(event) =>
                scope.setRange(event.target.value as (typeof RANGE_OPTIONS)[number]["value"])
              }
            >
              {RANGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>

      {summary ? (
        <p role="status" className="text-muted-foreground mt-2 text-sm">
          {summary}
        </p>
      ) : null}
    </div>
  );
}
