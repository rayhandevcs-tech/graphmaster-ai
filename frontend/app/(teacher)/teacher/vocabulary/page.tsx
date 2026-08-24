"use client";

import { Protected } from "@/components/auth/protected";
import { ComingSoon } from "@/components/layout/coming-soon";

export default function TeacherVocabularyPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <ComingSoon title="Vocabulary" sprint="Sprint 13">
        The seven categories and the terms in them. Terms are deactivated rather than deleted,
        because past scores still refer to them.
      </ComingSoon>
    </Protected>
  );
}
