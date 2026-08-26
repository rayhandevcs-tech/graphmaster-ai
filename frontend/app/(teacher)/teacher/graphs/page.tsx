"use client";

import { Protected } from "@/components/auth/protected";
import { GraphsManager } from "@/components/graphs/graphs-manager";

export default function TeacherGraphsPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <GraphsManager />
    </Protected>
  );
}
