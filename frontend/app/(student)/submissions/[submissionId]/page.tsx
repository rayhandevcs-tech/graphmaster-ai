import type { Metadata } from "next";

import { Protected } from "@/components/auth/protected";
import { ResultView } from "@/components/results/result-view";

export const metadata: Metadata = { title: "Your result" };

export default async function SubmissionResultPage({
  params,
}: {
  params: Promise<{ submissionId: string }>;
}) {
  const { submissionId } = await params;

  return (
    <Protected roles={["student"]}>
      <ResultView submissionId={submissionId} />
    </Protected>
  );
}
