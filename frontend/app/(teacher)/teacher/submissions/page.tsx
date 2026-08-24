"use client";

import { Protected } from "@/components/auth/protected";
import { ComingSoon } from "@/components/layout/coming-soon";

export default function TeacherSubmissionsPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <ComingSoon title="Submissions" sprint="Sprint 13">
        Review what your students wrote, what the marker detected, and what it did not.
      </ComingSoon>
    </Protected>
  );
}
