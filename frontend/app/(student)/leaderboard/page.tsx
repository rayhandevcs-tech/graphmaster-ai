"use client";

import { Protected } from "@/components/auth/protected";
import { ComingSoon } from "@/components/layout/coming-soon";

export default function LeaderboardPage() {
  return (
    <Protected roles={["student"]}>
      <ComingSoon title="Leaderboard" sprint="Sprint 13">
        Four boards — global, your class, this week and this month. Ranks and XP only: a reward tier
        never appears beside anyone&rsquo;s name.
      </ComingSoon>
    </Protected>
  );
}
