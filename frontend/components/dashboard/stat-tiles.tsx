import { ClipboardCheck, Target, TrendingUp, Trophy } from "lucide-react";

import { CountUp } from "@/components/motion/count-up";
import { Card } from "@/components/ui/card";
import { formatCount, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { StudentDashboard } from "@/types/api";

/**
 * The four figures that summarise a student's work.
 *
 * Cards, not a table. A table invites reading down a column, and there is no
 * column here — these are four unrelated measures, each of which wants to be
 * read on its own. The number is the largest thing in each tile and the label
 * sits under it, because the student already knows which four they are after
 * the first visit and is scanning for the values.
 *
 * A missing average renders as an em dash, never as zero: a student who has
 * not been marked yet has no average, and `0.0%` is a mark they would
 * reasonably believe they had been given.
 */
export function StatTiles({ dashboard }: { dashboard: StudentDashboard }) {
  const marked = dashboard.total_attempts > 0;

  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <StatTile
        icon={ClipboardCheck}
        label="Descriptions marked"
        value={dashboard.total_attempts}
        format={formatCount}
      />
      <StatTile
        icon={TrendingUp}
        label="Average score"
        value={marked ? dashboard.average_score : null}
        format={(value) => formatPercent(value)}
      />
      <StatTile
        icon={Trophy}
        label="Best score"
        value={marked ? dashboard.highest_score : null}
        format={(value) => formatPercent(value)}
      />
      <StatTile
        icon={Target}
        label="Target words used"
        value={marked ? dashboard.average_vocabulary_percentage : null}
        format={(value) => formatPercent(value)}
      />
    </div>
  );
}

function StatTile({
  icon: Icon,
  label,
  value,
  format,
  className,
}: {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  label: string;
  value: number | null;
  format: (value: number) => string;
  className?: string;
}) {
  return (
    <Card className={cn("flex flex-col gap-3 p-4 sm:p-5", className)}>
      <span className="bg-muted text-muted-foreground flex size-8 items-center justify-center rounded-lg">
        <Icon className="size-4" aria-hidden />
      </span>

      <div className="flex flex-col gap-0.5">
        <span className="text-2xl leading-none font-semibold tabular-nums sm:text-3xl">
          {value === null ? "—" : <CountUp value={value} format={format} />}
        </span>
        <span className="text-muted-foreground text-xs sm:text-sm">{label}</span>
      </div>
    </Card>
  );
}
