"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LineChart } from "lucide-react";

import { useAuth } from "@/lib/auth/context";
import { isAdmin, isStudent, isTeacherOrAdmin } from "@/lib/auth/roles";
import { cn } from "@/lib/utils";
import type { UserRole } from "@/types/api";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { UserMenu } from "@/components/layout/user-menu";

interface NavLink {
  href: string;
  label: string;
}

/** Sprint 11 onwards fill these routes in; the header knows about them now so
 *  the navigation does not have to be rebuilt around each new page. */
function linksFor(role: UserRole | undefined): NavLink[] {
  if (isStudent(role)) {
    return [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/practice", label: "Practice" },
      { href: "/leaderboard", label: "Leaderboard" },
      { href: "/achievements", label: "Achievements" },
    ];
  }
  if (isTeacherOrAdmin(role)) {
    const links = [
      { href: "/teacher/dashboard", label: "Dashboard" },
      { href: "/teacher/submissions", label: "Submissions" },
      { href: "/teacher/graphs", label: "Graphs" },
      { href: "/teacher/vocabulary", label: "Vocabulary" },
      { href: "/teacher/analytics", label: "Analytics" },
    ];
    if (isAdmin(role)) links.push({ href: "/admin/users", label: "Users" });
    return links;
  }
  return [];
}

export function SiteHeader() {
  const { user } = useAuth();
  const pathname = usePathname();
  const links = linksFor(user?.role);

  return (
    <header className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link href={user ? "/dashboard" : "/"} className="flex items-center gap-2 font-semibold">
          <LineChart className="text-primary size-5" aria-hidden />
          <span>GraphMaster</span>
        </Link>

        <nav aria-label="Main" className="hidden flex-1 items-center gap-1 md:flex">
          {links.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-1">
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
