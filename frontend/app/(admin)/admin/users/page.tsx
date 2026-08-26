"use client";

import { Protected } from "@/components/auth/protected";
import { UsersManager } from "@/components/admin/users-manager";

export default function AdminUsersPage() {
  return (
    <Protected roles={["admin"]}>
      <UsersManager />
    </Protected>
  );
}
