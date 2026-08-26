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
}: {
  params: Promise<{ graphId: string }>;
}) {
  const { graphId } = await params;

  return (
    <Protected roles={["student"]}>
      <PracticeWorkspace graphId={graphId} />
    </Protected>
  );
}
