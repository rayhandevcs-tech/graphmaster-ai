"use client";

/**
 * Route protection.
 *
 * This decides what the interface *shows*. It is not what keeps a student out
 * of a teacher's data — every endpoint demands a token and checks the role
 * server-side, and the backend's surface test proves it for all 75 of them. A
 * guard here that failed open would leak a layout, not a record.
 *
 * It runs in the browser rather than in middleware because the two credentials
 * involved are both unavailable to a Next server: the access token lives in
 * memory in the tab, and the refresh cookie belongs to the API's origin, so it
 * is not sent to the frontend's own host in a split deployment.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ShieldAlert } from "lucide-react";

import { useAuth } from "@/lib/auth/context";
import { homePathForRole, ROLE_LABELS } from "@/lib/auth/roles";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { UserRole } from "@/types/api";

export interface ProtectedProps {
  /** Omit to require only that someone is signed in. */
  roles?: readonly UserRole[];
  children: React.ReactNode;
}

export function Protected({ roles, children }: ProtectedProps) {
  const { status, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status !== "anonymous") return;
    // Where they were going, so signing in resumes it rather than dropping
    // them on a dashboard.
    const here = window.location.pathname + window.location.search;
    router.replace(`/login?next=${encodeURIComponent(here)}`);
  }, [status, router]);

  if (status === "loading" || status === "anonymous") {
    return (
      <div className="flex min-h-[50vh] items-center justify-center" aria-busy>
        <Spinner label="Checking your session" />
      </div>
    );
  }

  if (roles && user && !roles.includes(user.role)) {
    return <WrongRole role={user.role} />;
  }

  return <>{children}</>;
}

/**
 * A wrong role is a dead end, not a redirect.
 *
 * Bouncing a student to their dashboard from a teacher URL leaves them
 * wondering whether they mistyped; saying so, with the way back, does not.
 */
function WrongRole({ role }: { role: UserRole }) {
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <ShieldAlert className="text-muted-foreground size-10" aria-hidden />
      <h1 className="text-xl font-semibold">This page is not for your account</h1>
      <p className="text-muted-foreground text-sm">
        You are signed in as a {ROLE_LABELS[role].toLowerCase()}, and this page belongs to a
        different role.
      </p>
      <Button asChild variant="outline">
        <Link href={homePathForRole(role)}>Go to your home page</Link>
      </Button>
    </div>
  );
}

/**
 * Conditional UI rather than a whole page: hides a teacher-only link from a
 * student instead of showing them a control that will be refused.
 */
export function RoleGate({
  roles,
  children,
  fallback = null,
}: {
  roles: readonly UserRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) return <>{fallback}</>;
  return <>{children}</>;
}
