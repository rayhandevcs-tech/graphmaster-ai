import { CheckCircle2, CircleDashed, FileText, TriangleAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { SubmissionStatus } from "@/types/api";

/**
 * What state an attempt is in, in a word.
 *
 * `failed` is the one that needs care. It means recognition could not read the
 * handwriting — **not** that the student failed, and not that the attempt is
 * over: a student can type into a submission whose recognition failed, and the
 * record still shows that handwriting was attempted (CLAUDE.md rule 20). So it
 * is worded as a fact about the photograph, never about the person.
 */
const CHIP: Record<SubmissionStatus, { label: string; icon: typeof FileText; className: string }> =
  {
    draft: { label: "Draft", icon: FileText, className: "bg-muted text-muted-foreground" },
    extracting: {
      label: "Reading…",
      icon: CircleDashed,
      className: "bg-muted text-muted-foreground",
    },
    analyzing: {
      label: "Marking…",
      icon: CircleDashed,
      className: "bg-muted text-muted-foreground",
    },
    extracted: {
      label: "Ready to mark",
      icon: CircleDashed,
      className: "bg-secondary/15 text-secondary",
    },
    scored: { label: "Marked", icon: CheckCircle2, className: "bg-success/15 text-success" },
    failed: {
      label: "Not recognised",
      icon: TriangleAlert,
      className: "bg-destructive/15 text-destructive",
    },
  };

export function StatusChip({
  status,
  className,
}: {
  status: SubmissionStatus;
  className?: string;
}) {
  const chip = CHIP[status] ?? CHIP.draft;
  const Icon = chip.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        chip.className,
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {chip.label}
    </span>
  );
}
