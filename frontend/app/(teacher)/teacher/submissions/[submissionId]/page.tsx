"use client";

import { use } from "react";

import { Protected } from "@/components/auth/protected";
import { SubmissionReview } from "@/components/submissions/submission-review";

export default function TeacherSubmissionPage({
  params,
}: {
  params: Promise<{ submissionId: string }>;
}) {
  const { submissionId } = use(params);

  return (
    <Protected roles={["teacher", "admin"]}>
      <SubmissionReview submissionId={submissionId} />
    </Protected>
  );
}
