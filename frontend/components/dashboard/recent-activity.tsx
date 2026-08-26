import Link from "next/link";
import { ArrowUpRight, History } from "lucide-react";

import { GraphTypeIcon, GRAPH_TYPE_LABELS } from "@/components/practice/graph-meta";
import { TierMark, TIER_LABELS } from "@/components/gamification/tiers";
import { EmptyState } from "@/components/layout/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent, formatWhen } from "@/lib/format";
import type { RecentActivity as RecentActivityItem } from "@/types/api";

/**
 * The last few marked descriptions.
 *
 * Rows rather than a table, and each row is a link to the full result. A table
 * of five items is a table because the data came in rows, not because anyone
 * wants to compare them column by column — and a table cell cannot be a
 * comfortable tap target on a phone, which these have to be.
 *
 * The tier is shown as its mark and its name together. It is the student's own
 * result page in miniature, and the practice tier reads here exactly as it
 * does there: a stage, not a verdict.
 */
export function RecentActivity({ items }: { items: RecentActivityItem[] }) {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
        <div className="flex flex-col gap-1.5">
          <CardTitle>Recent work</CardTitle>
          <CardDescription>Your last few marked descriptions.</CardDescription>
        </div>
        {items.length > 0 ? (
          <Button asChild variant="ghost" size="sm" className="shrink-0">
            <Link href="/practice">
              Practise more
              <ArrowUpRight aria-hidden />
            </Link>
          </Button>
        ) : null}
      </CardHeader>

      <CardContent className="flex-1">
        {items.length === 0 ? (
          <EmptyState
            icon={History}
            title="No marked work yet"
            description="Descriptions you finish are marked straight away, and the results land here."
            action={
              <Button asChild size="sm">
                <Link href="/practice">Choose a graph</Link>
              </Button>
            }
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {items.map((item) => (
              <li key={item.submission_id}>
                <Link
                  href={`/submissions/${item.submission_id}`}
                  className="hover:bg-accent/60 focus-visible:bg-accent/60 flex items-center gap-3 rounded-lg p-2 transition-colors"
                >
                  <TierMark tier={item.reward_tier} className="size-9" iconClassName="size-4" />

                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{item.graph_title}</span>
                    <span className="text-muted-foreground flex items-center gap-1.5 text-xs">
                      <GraphTypeIcon graphType={item.graph_type} className="size-3" />
                      {GRAPH_TYPE_LABELS[item.graph_type]}
                      <span aria-hidden>·</span>
                      {formatWhen(item.scored_at)}
                    </span>
                  </span>

                  <span className="shrink-0 text-right">
                    <span className="block text-sm font-semibold tabular-nums">
                      {formatPercent(item.final_score, 0)}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {TIER_LABELS[item.reward_tier]}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
