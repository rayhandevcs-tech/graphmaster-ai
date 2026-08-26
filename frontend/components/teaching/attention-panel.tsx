"use client";

import { useState } from "react";
import { CircleSlash, Clock, TrendingDown } from "lucide-react";

import { StudentRowLink, hardDetail, quietDetail } from "./student-row";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { triage, attentionCount, type AttentionGroupId } from "@/lib/insights/attention";
import { cn } from "@/lib/utils";
import type { StudentRow } from "@/types/api";

/**
 * Who needs the teacher, above everything else on the screen.
 *
 * This panel is the answer to the question a teacher actually opens the
 * product with, and it is deliberately the first thing on the page — before
 * any average, any chart and any total. A statistics-first dashboard tells
 * someone their class averages 61, which is true and changes nothing about
 * what they do next.
 *
 * The grouping and its order come from `lib/insights/attention.ts`, where they
 * are tested. This file decides only how they look.
 */
const GROUP_ICON: Record<AttentionGroupId, React.ComponentType<{ className?: string }>> = {
  "never-started": CircleSlash,
  "finding-it-hard": TrendingDown,
  "gone-quiet": Clock,
};

/**
 * The dot beside a group name.
 *
 * It repeats what the label already says. A teacher scanning the panel finds
 * the group by colour; a colour-blind one reads the same thing in the words,
 * and nothing here is encoded in the colour alone (NFR-4.6).
 */
const GROUP_DOT: Record<AttentionGroupId, string> = {
  "never-started": "bg-muted-foreground",
  "finding-it-hard": "bg-destructive",
  "gone-quiet": "bg-secondary",
};

/** Rows shown before the group collapses behind a "show all". */
const PREVIEW_ROWS = 4;

export function AttentionPanel({
  students,
  className,
}: {
  students: StudentRow[];
  className?: string;
}) {
  const groups = triage(students);
  const total = attentionCount(groups);

  if (total === 0) {
    return (
      <Card className={cn("flex flex-col gap-2 p-6", className)}>
        <h2 className="text-base font-semibold tracking-tight">Nobody needs chasing</h2>
        <p className="text-muted-foreground text-sm text-pretty">
          Every student in this class has started, is averaging above the practice band, and has
          worked in the last week.
        </p>
      </Card>
    );
  }

  return (
    <Card className={cn("flex flex-col gap-5 p-6", className)}>
      <div className="flex flex-col gap-1">
        <h2 className="text-base font-semibold tracking-tight">
          {total === 1 ? "1 student needs you" : `${total} students need you`}
        </h2>
        <p className="text-muted-foreground text-sm text-pretty">
          Ordered by what you can act on today. Each student appears once.
        </p>
      </div>

      {groups.map((group) => (
        <AttentionGroup key={group.id} group={group} />
      ))}
    </Card>
  );
}

function AttentionGroup({ group }: { group: ReturnType<typeof triage>[number] }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = GROUP_ICON[group.id];
  const visible = expanded ? group.entries : group.entries.slice(0, PREVIEW_ROWS);
  const hidden = group.entries.length - visible.length;

  return (
    <section className="flex flex-col gap-2">
      <h3 className="flex items-center gap-2 text-xs font-semibold tracking-wide uppercase">
        <span className={cn("size-2 rounded-full", GROUP_DOT[group.id])} aria-hidden />
        <Icon className="text-muted-foreground size-3.5" aria-hidden />
        {group.label}
        <span className="text-muted-foreground tabular-nums">· {group.entries.length}</span>
      </h3>
      <p className="text-muted-foreground sr-only">{group.description}</p>

      <ul className="border-border/60 flex flex-col rounded-lg border">
        {visible.map((entry) => (
          <StudentRowLink
            key={entry.student.user_id}
            student={entry.student}
            detail={detailFor(group.id, entry.student)}
          />
        ))}
      </ul>

      {hidden > 0 ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(true)}
          className="text-muted-foreground w-fit"
        >
          Show all {group.entries.length}
        </Button>
      ) : null}
    </section>
  );
}

function detailFor(group: AttentionGroupId, student: StudentRow): string {
  if (group === "never-started") return "No marked work yet";
  if (group === "finding-it-hard") return hardDetail(student);
  return quietDetail(student);
}
