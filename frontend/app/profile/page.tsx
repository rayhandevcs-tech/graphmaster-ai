"use client";

import { Protected } from "@/components/auth/protected";
import { ComingSoon } from "@/components/layout/coming-soon";

export default function ProfilePage() {
  return (
    <Protected roles={["student", "teacher", "admin"]}>
      <ComingSoon title="Profile" sprint="Sprint 11">
        Your name, your avatar and your password. Choosing a new avatar needs the catalogue screen,
        which arrives with the rest of the student experience.
      </ComingSoon>
    </Protected>
  );
}
