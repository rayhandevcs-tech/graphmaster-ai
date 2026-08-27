"use client";

import { use } from "react";

import { Protected } from "@/components/auth/protected";
import { AssignmentProgressView } from "@/components/assignments/assignment-progress";

export default function TeacherAssignmentPage({
  params,
}: {
  params: Promise<{ assignmentId: string }>;
}) {
  const { assignmentId } = use(params);

  return (
    <Protected roles={["teacher", "admin"]}>
      <AssignmentProgressView assignmentId={assignmentId} />
    </Protected>
  );
}
