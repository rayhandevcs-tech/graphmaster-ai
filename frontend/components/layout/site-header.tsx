"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LineChart } from "lucide-react";

import { useAuth } from "@/lib/auth/context";
import { homePathForRole } from "@/lib/auth/roles";
import { isActive, linksFor } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { UserMenu } from "@/components/layout/user-menu";

export function SiteHeader() {
  const { user } = useAuth();
  const pathname = usePathname();
  const links = linksFor(user?.role);

  return (
    <header className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center gap-4 px-4 sm:px-6">
        {/* A teacher's home is not the student dashboard, and sending them
            there is a role error dressed up as a link. */}
        <Link
          href={user ? homePathForRole(user.role) : "/"}
          className="flex items-center gap-2 font-semibold"
        >
          <LineChart className="text-primary size-5" aria-hidden />
          <span>GraphMaster</span>
        </Link>

        {/* Below `md` the links move to the bar at the bottom of the screen,
            which is where a thumb reaches. Two navigations, one list. */}
        <nav aria-label="Main" className="hidden flex-1 items-center gap-1 md:flex">
          {links.map((link) => {
            const active = isActive(pathname, link.href);
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
