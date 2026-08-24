"use client";

import { Protected } from "@/components/auth/protected";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Administrator-only. The role list is the whole point of the guard here. */
export default function AdminUsersPage() {
  return (
    <Protected roles={["admin"]}>
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <Card>
          <CardHeader>
            <CardTitle>User management</CardTitle>
            <CardDescription>
              Roles, class assignment and account status — sprint 13.
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      </div>
    </Protected>
  );
}
