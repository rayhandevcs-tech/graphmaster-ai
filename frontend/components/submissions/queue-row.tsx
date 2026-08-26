import Link from "next/link";
import { ChevronRight, Keyboard, PenLine } from "lucide-react";

import { StatusChip } from "./status-chip";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { TableCell, TableRow } from "@/components/ui/table";
import { formatPercent, formatWhen, initials } from "@/lib/format";
import type { SubmissionSummary } from "@/types/api";

/**
 * One attempt in the queue — as a card on a phone, a table row on a desktop.
 *
 * Both presentations carry the same four facts, and they are the four that let
 * a teacher decide which to open without opening any: who, which graph, how it
 * was written, and what it scored.
 *
 * **The score is `—` when there is none, never `0`.** An unmarked attempt and
 * a bad one are different things, and the row says which by pairing the dash
 * with the status.
 *
 * **`input_method` never flips** (CLAUDE.md rule 20). A handwritten submission
 * whose recognition failed still shows the pen, even after the student typed
 * their answer instead — the record is that handwriting was attempted and did
 * not read.
 */
function Method({ summary }: { summary: SubmissionSummary }) {
  const handwritten = summary.input_method === "handwriting";
  const Icon = handwritten ? PenLine : Keyboard;
  return (
    <span className="text-muted-foreground inline-flex items-center gap-1.5 text-xs">
      <Icon className="size-3.5" aria-hidden />
      {handwritten ? "Handwritten" : "Typed"}
    </span>
  );
}

function Score({ summary }: { summary: SubmissionSummary }) {
  const value = formatPercent(summary.final_score, 0);
  return (
    <span className="text-sm font-semibold tabular-nums">
      {value}
      {value === "—" ? <span className="sr-only">not marked</span> : null}
    </span>
  );
}

export function QueueCard({ summary }: { summary: SubmissionSummary }) {
  return (
    <li>
      <Link
        href={`/teacher/submissions/${summary.id}`}
        className="hover:bg-muted/50 focus-visible:ring-ring flex min-h-16 items-center gap-3 rounded-lg border p-3 transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        <Avatar className="size-9 shrink-0">
          <AvatarFallback className="text-xs">
            {initials(summary.student_name ?? "?")}
          </AvatarFallback>
        </Avatar>

        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="truncate text-sm font-medium">{summary.student_name ?? "Unknown"}</span>
          <span className="text-muted-foreground truncate text-xs">
            {summary.graph_title ?? "Untitled graph"}
          </span>
          <span className="flex flex-wrap items-center gap-2">
            <StatusChip status={summary.status} />
            <Method summary={summary} />
            <span className="text-muted-foreground text-xs">
              {formatWhen(summary.scored_at ?? summary.submitted_at)}
            </span>
          </span>
        </span>

        <span className="flex shrink-0 items-center gap-2">
          <Score summary={summary} />
          <ChevronRight className="text-muted-foreground size-4" aria-hidden />
        </span>
      </Link>
    </li>
  );
}

export function QueueRow({ summary }: { summary: SubmissionSummary }) {
  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-2">
          <Avatar className="size-7 shrink-0">
            <AvatarFallback className="text-[10px]">
              {initials(summary.student_name ?? "?")}
            </AvatarFallback>
          </Avatar>
          <span className="text-sm font-medium">{summary.student_name ?? "Unknown"}</span>
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground max-w-56 truncate text-sm">
        {summary.graph_title ?? "Untitled graph"}
      </TableCell>
      <TableCell>
        <Method summary={summary} />
      </TableCell>
      <TableCell>
        <StatusChip status={summary.status} />
      </TableCell>
      <TableCell className="text-right">
        <Score summary={summary} />
      </TableCell>
      <TableCell className="text-muted-foreground text-right text-xs whitespace-nowrap">
        {formatWhen(summary.scored_at ?? summary.submitted_at)}
      </TableCell>
      <TableCell className="text-right">
        <Link
          href={`/teacher/submissions/${summary.id}`}
          className="text-primary focus-visible:ring-ring inline-flex items-center rounded text-sm font-medium hover:underline focus-visible:ring-2 focus-visible:outline-none"
        >
          Open
          <ChevronRight className="size-4" aria-hidden />
        </Link>
      </TableCell>
    </TableRow>
  );
}
