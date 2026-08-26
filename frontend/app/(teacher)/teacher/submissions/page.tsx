"use client";

import { Suspense } from "react";

import { Protected } from "@/components/auth/protected";
import { SubmissionQueue } from "@/components/submissions/submission-queue";
import { Skeleton } from "@/components/ui/skeleton";

export default function TeacherSubmissionsPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      {/* `useSearchParams` needs a boundary: without one the whole route opts
          out of static rendering at build time. */}
      <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
        <SubmissionQueue />
      </Suspense>
    </Protected>
  );
}
