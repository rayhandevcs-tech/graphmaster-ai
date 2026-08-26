import {
  BarChart3,
  BookOpen,
  ClipboardList,
  LayoutDashboard,
  LineChart,
  Medal,
  PenLine,
  Trophy,
  Users,
} from "lucide-react";

import { isAdmin, isStudent, isTeacherOrAdmin } from "@/lib/auth/roles";
import type { UserRole } from "@/types/api";

/**
 * The navigation, in one place.
 *
 * The header and the phone's bottom bar render the same list. Two copies drift
 * — a route added to one and not the other is invisible on exactly the device
 * whose users were not asked about it — and the icons matter to both: the
 * bottom bar has no room for a label wider than a thumb.
 */
export interface NavLink {
  href: string;
  label: string;
  /** Shown on the phone's bar, and beside nothing on the desktop header. */
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  /** A shorter label for the bottom bar, where four have to fit across. */
  shortLabel?: string;
}

export function linksFor(role: UserRole | undefined): NavLink[] {
  if (isStudent(role)) {
    return [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, shortLabel: "Home" },
      { href: "/practice", label: "Practice", icon: PenLine },
      { href: "/leaderboard", label: "Leaderboard", icon: Trophy, shortLabel: "Ranks" },
      { href: "/achievements", label: "Achievements", icon: Medal, shortLabel: "Awards" },
    ];
  }

  if (isTeacherOrAdmin(role)) {
    const links: NavLink[] = [
      { href: "/teacher/dashboard", label: "Dashboard", icon: LayoutDashboard, shortLabel: "Home" },
      {
        href: "/teacher/submissions",
        label: "Submissions",
        icon: ClipboardList,
        shortLabel: "Work",
      },
      { href: "/teacher/graphs", label: "Graphs", icon: LineChart },
      { href: "/teacher/vocabulary", label: "Vocabulary", icon: BookOpen, shortLabel: "Words" },
      { href: "/teacher/analytics", label: "Analytics", icon: BarChart3, shortLabel: "Data" },
    ];
    if (isAdmin(role)) links.push({ href: "/admin/users", label: "Users", icon: Users });
    return links;
  }

  return [];
}

/** Whether a link is the one the current path belongs to. */
export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
