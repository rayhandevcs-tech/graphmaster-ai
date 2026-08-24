"use client";

import { Protected } from "@/components/auth/protected";
import { ComingSoon } from "@/components/layout/coming-soon";

export default function AchievementsPage() {
  return (
    <Protected roles={["student"]}>
      <ComingSoon title="Achievements" sprint="Sprint 12">
        Every achievement you have unlocked, and how far you are from the ones you have not.
      </ComingSoon>
    </Protected>
  );
}
