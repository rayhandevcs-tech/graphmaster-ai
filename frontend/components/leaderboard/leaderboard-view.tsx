"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Trophy } from "lucide-react";

import { Podium } from "./podium";
import { RankRow } from "./rank-row";
import { YourRank } from "./your-rank";
import { EmptyState } from "@/components/layout/empty-state";
import { Pager } from "@/components/layout/pager";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage, leaderboardApi, queryKeys } from "@/lib/api";
import { useAuth } from "@/lib/auth/context";
import { formatLongDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { LeaderboardScope } from "@/types/api";

/**
 * The board, and the one screen in this product allowed to be loud.
 *
 * Two rules hold it together. **No reward tier appears anywhere** (FR-7.6): a
 * hammer count belongs on one student's own results screen, and beside a name
 * in front of the cohort it is the humiliation the whole reward design avoids.
 * And **the student's own standing is always visible**, pinned to the bottom,
 * whether they are third or ninetieth or not ranked at all.
 *
 * The four scopes are chips rather than a picker: they are the whole
 * interaction, they fit on one line, and a student comparing "this week"
 * against "all time" should be able to flip between them in one tap each way.
 */
const SCOPES: { value: LeaderboardScope; label: string }[] = [
  { value: "weekly", label: "This week" },
  { value: "monthly", label: "This month" },
  { value: "class", label: "My class" },
  { value: "global", label: "All time" },
];

const PAGE_SIZE = 20;

export function LeaderboardView() {
  const { user } = useAuth();
  const [scope, setScope] = useState<LeaderboardScope>("weekly");
  const [page, setPage] = useState(1);

  // A student with no class has no class board. Offering the chip and then
  // showing nothing reads as a fault; omitting it reads as what it is.
  const scopes = SCOPES.filter((option) => option.value !== "class" || Boolean(user?.class_id));

  const board = useQuery({
    queryKey: queryKeys.leaderboard({ scope, page, page_size: PAGE_SIZE }),
    queryFn: () => leaderboardApi.page({ scope, page, page_size: PAGE_SIZE }),
    placeholderData: (previous) => previous,
  });

  const position = useQuery({
    queryKey: queryKeys.leaderboardPosition({ scope }),
    queryFn: () => leaderboardApi.me({ scope }),
  });

  const entries = board.data?.entries ?? [];
  const onPodium = page === 1 ? entries.slice(0, 3) : [];
  const listed = page === 1 ? entries.slice(3) : entries;

  const mine = position.data?.entry ?? null;
  const above = mine ? (entries.find((entry) => entry.rank === mine.rank - 1) ?? null) : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Leaderboard</h1>
        <p className="text-muted-foreground text-sm">
          Ranked on the XP you earn by practising. Your scores stay yours.
        </p>
      </div>

      <div role="group" aria-label="Board" className="flex flex-wrap gap-1.5">
        {scopes.map((option) => {
          const active = option.value === scope;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={active}
              onClick={() => {
                setScope(option.value);
                setPage(1);
              }}
              className={cn(
                "focus-visible:ring-ring min-h-11 rounded-full border px-4 text-sm font-medium sm:min-h-9",
                "transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none",
                active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:border-input hover:text-foreground",
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {board.isPending ? (
        <BoardSkeleton />
      ) : board.isError ? (
        <Alert variant="destructive">
          <AlertTitle>The board could not be loaded</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-3">
            <span>{errorMessage(board.error)}</span>
            <Button variant="outline" size="sm" onClick={() => void board.refetch()}>
              <RefreshCw aria-hidden />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      ) : entries.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="Nobody is on this board yet"
          description="It fills up as your class practises. The first marked description of the period puts someone at the top."
          action={
            <Button asChild size="sm">
              <Link href="/practice">Choose a graph</Link>
            </Button>
          }
        />
      ) : (
        <>
          <p role="status" className="text-muted-foreground text-sm">
            {board.data
              ? `${board.data.total.toLocaleString()} ranked · ${formatLongDate(
                  board.data.period.period_start,
                )} to ${formatLongDate(board.data.period.period_end)}`
              : ""}
          </p>

          {onPodium.length > 0 ? (
            <Card className="px-4 py-8 sm:px-8">
              <Podium entries={onPodium} />
            </Card>
          ) : null}

          <ul className="flex flex-col gap-1">
            {listed.map((entry) => (
              <RankRow key={entry.user_id} entry={entry} />
            ))}
          </ul>

          {board.data && board.data.total_pages > 1 ? (
            <Pager
              page={board.data.page}
              totalPages={board.data.total_pages}
              total={board.data.total}
              onPageChange={setPage}
              itemNoun="students"
            />
          ) : null}
        </>
      )}

      {position.data ? <YourRank position={position.data} above={above} /> : null}
    </div>
  );
}

function BoardSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy>
      <span className="sr-only" role="status">
        Loading the leaderboard
      </span>
      <Skeleton className="h-48 rounded-xl" />
      {[0, 1, 2, 3, 4].map((index) => (
        <Skeleton key={index} className="h-14 rounded-lg" />
      ))}
    </div>
  );
}
