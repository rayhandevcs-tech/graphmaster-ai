"use client";

import { Protected } from "@/components/auth/protected";
import { ComingSoon } from "@/components/layout/coming-soon";

export default function PracticePage() {
  return (
    <Protected roles={["student"]}>
      <ComingSoon title="Practice" sprint="Sprint 11">
        Pick a graph, read the chart, and write your description — typed, or photographed from a
        handwritten page and corrected before it is marked.
      </ComingSoon>
    </Protected>
  );
}
