"use client";

import { Protected } from "@/components/auth/protected";
import { AnalyticsView } from "@/components/analytics/analytics-view";

export default function TeacherAnalyticsPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <AnalyticsView />
    </Protected>
  );
}
