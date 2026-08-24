"use client";

import { Protected } from "@/components/auth/protected";
import { ComingSoon } from "@/components/layout/coming-soon";

export default function TeacherGraphsPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <ComingSoon title="Graphs" sprint="Sprint 13">
        Author practice charts and curate the target vocabulary each one is marked against.
      </ComingSoon>
    </Protected>
  );
}
