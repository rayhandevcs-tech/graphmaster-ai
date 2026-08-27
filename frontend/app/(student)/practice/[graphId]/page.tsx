import type { Metadata } from "next";

import { Protected } from "@/components/auth/protected";
import { PracticeWorkspace } from "@/components/practice/practice-workspace";

export const metadata: Metadata = { title: "Practice" };

/**
 * A server component for the one thing the server can do here: read the route
 * parameter. Everything below it needs the access token, which lives in memory
 * in the tab and is never available to a Next server (06-frontend-architecture
 * §6.2), so the workspace itself is a client component.
 */
export default async function GraphPracticePage({
  params,
  searchParams,
}: {
  params: Promise<{ graphId: string }>;
  searchParams: Promise<{ assignment?: string }>;
}) {
  const { graphId } = await params;
  // Read here rather than with `useSearchParams` below: the workspace opens a
  // submission on the student's first keystroke, and the assignment has to be
  // known by then — `assignment_id` is set at creation and never updated.
  const { assignment } = await searchParams;

  return (
    <Protected roles={["student"]}>
      <PracticeWorkspace graphId={graphId} assignmentId={assignment ?? null} />
    </Protected>
  );
}
