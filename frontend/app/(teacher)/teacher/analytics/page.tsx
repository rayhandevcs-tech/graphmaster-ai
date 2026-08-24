"use client";

import { Protected } from "@/components/auth/protected";
import { ComingSoon } from "@/components/layout/coming-soon";

export default function TeacherAnalyticsPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <ComingSoon title="Analytics" sprint="Sprint 13">
        Class averages, score trends, the vocabulary your students reach for, and the students who
        have not started.
      </ComingSoon>
    </Protected>
  );
}
