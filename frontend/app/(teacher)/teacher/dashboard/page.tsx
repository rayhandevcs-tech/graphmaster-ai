"use client";

import { Protected } from "@/components/auth/protected";
import { TeacherDashboard } from "@/components/teaching/teacher-dashboard";

export default function TeacherDashboardPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <TeacherDashboard />
    </Protected>
  );
}
