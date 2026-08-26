"use client";

import { Protected } from "@/components/auth/protected";
import { ProfileView } from "@/components/profile/profile-view";

export default function ProfilePage() {
  return (
    <Protected roles={["student", "teacher", "admin"]}>
      <ProfileView />
    </Protected>
  );
}
