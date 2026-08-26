"use client";

import { Protected } from "@/components/auth/protected";
import { SettingsView } from "@/components/settings/settings-view";

export default function SettingsPage() {
  return (
    <Protected roles={["student", "teacher", "admin"]}>
      <SettingsView />
    </Protected>
  );
}
