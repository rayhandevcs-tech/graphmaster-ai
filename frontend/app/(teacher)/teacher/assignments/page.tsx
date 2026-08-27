"use client";

import { Protected } from "@/components/auth/protected";
import { AssignmentsManager } from "@/components/assignments/assignments-manager";

export default function TeacherAssignmentsPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <AssignmentsManager />
    </Protected>
  );
}
