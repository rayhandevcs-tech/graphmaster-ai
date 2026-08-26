"use client";

import { Protected } from "@/components/auth/protected";
import { LeaderboardView } from "@/components/leaderboard/leaderboard-view";

export default function LeaderboardPage() {
  return (
    <Protected roles={["student"]}>
      <LeaderboardView />
    </Protected>
  );
}
