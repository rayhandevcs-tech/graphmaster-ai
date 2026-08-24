"use client";

import { Protected } from "@/components/auth/protected";
import { useAuth } from "@/lib/auth/context";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * The student's home.
 *
 * Sprint 11 fills this with the dashboard aggregate — attempts, average,
 * streak, recent activity and the score trend, all of which
 * `GET /users/me/dashboard` already returns. What is here now is the part
 * sprint 10 is responsible for: that a signed-in student, and only a signed-in
 * student, reaches this route with their profile loaded.
 */
export default function DashboardPage() {
  return (
    <Protected roles={["student"]}>
      <SessionSummary />
    </Protected>
  );
}

function SessionSummary() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Hello, {user.full_name}</h1>
        <p className="text-muted-foreground text-sm">
          {ROLE_LABELS[user.role]} · Level {user.current_level}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your session</CardTitle>
          <CardDescription>
            Loaded from <code>GET /users/me</code> after the refresh cookie was exchanged for an
            access token.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <Stat label="Total XP" value={user.total_xp.toLocaleString()} />
          <Stat label="Current streak" value={`${user.current_streak_days} days`} />
          <Stat label="Longest streak" value={`${user.longest_streak_days} days`} />
        </CardContent>
      </Card>

      <p className="text-muted-foreground text-sm">
        <Badge variant="muted">Sprint 11</Badge> Practice, results and the reward animations arrive
        next.
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-muted-foreground text-xs tracking-wide uppercase">{label}</span>
      <span className="text-2xl font-semibold">{value}</span>
    </div>
  );
}
