"use client";

import { Protected } from "@/components/auth/protected";
import { AchievementsView } from "@/components/achievements/achievements-view";

export default function AchievementsPage() {
  return (
    <Protected roles={["student"]}>
      <AchievementsView />
    </Protected>
  );
}
