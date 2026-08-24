"use client";

import { Protected } from "@/components/auth/protected";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Sprint 13 builds the teaching surfaces; the route and its guard exist now. */
export default function TeacherDashboardPage() {
  return (
    <Protected roles={["teacher", "admin"]}>
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight">Teaching</h1>
        <Card>
          <CardHeader>
            <CardTitle>Class overview</CardTitle>
            <CardDescription>
              Submission review, the vocabulary manager, analytics and exports arrive in sprint 13.
              Every figure they will show is already served by the API.
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      </div>
    </Protected>
  );
}
