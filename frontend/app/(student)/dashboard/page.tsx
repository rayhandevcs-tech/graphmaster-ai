"use client";

import { Protected } from "@/components/auth/protected";
import { DashboardView } from "@/components/dashboard/dashboard-view";

/**
 * The student's home (FR-10.1 – FR-10.5).
 *
 * A client route rather than a server one: everything on it belongs to the
 * signed-in student, and the credential that identifies them is an access
 * token held in the tab's memory — a Next server rendering this page has no
 * way to read it (06-frontend-architecture §5).
 */
export default function DashboardPage() {
  return (
    <Protected roles={["student"]}>
      <DashboardView />
    </Protected>
  );
}
