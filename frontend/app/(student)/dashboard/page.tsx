"use client";

import Link from "next/link";

import { Protected } from "@/components/auth/protected";
import { useAuth } from "@/lib/auth/context";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * The student's home.
 *
 * Still the sprint 10 version: proof that a signed-in student, and only a
 * signed-in student, reaches this route with their profile loaded. The
 * dashboard aggregate — attempts, average, streak, recent activity and the
 * score trend, all of which `GET /users/me/dashboard` already returns — is
 * the next thing to land here. Sprint 11 built the practice loop instead,
 * because a student could sign in but not practise.
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

      <p className="text-muted-foreground flex flex-wrap items-center gap-2 text-sm">
        <Badge variant="muted">Sprint 12</Badge>
        <span>
          The attempts, average and score trend land here next, with the reward animations.{" "}
          <Link href="/practice" className="text-primary underline-offset-4 hover:underline">
            Practice is ready now.
          </Link>
        </span>
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
