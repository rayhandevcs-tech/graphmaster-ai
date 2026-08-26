"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth/context";
import { isActive, linksFor } from "@/lib/nav";
import { cn } from "@/lib/utils";

/**
 * The navigation on a phone.
 *
 * The header's links are hidden below `md` — there is no room for them beside
 * the logo — so without this a student on a phone can reach the dashboard and
 * nothing else. A bar at the bottom rather than a hamburger at the top: the
 * destinations here are the four things a student does, they are reached
 * constantly, and the bottom of the screen is the part of a phone a thumb can
 * actually reach.
 *
 * `pb-[env(safe-area-inset-bottom)]` keeps the row clear of the home
 * indicator on a phone that has one; without it the bottom row of targets sits
 * under a system gesture area and swallows every second tap.
 */
export function MobileNav() {
  const { user } = useAuth();
  const pathname = usePathname();
  const links = linksFor(user?.role);

  if (links.length === 0) return null;

  return (
    <nav
      aria-label="Main"
      className="bg-background/95 supports-[backdrop-filter]:bg-background/85 fixed inset-x-0 bottom-0 z-40 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      <ul className="mx-auto flex max-w-lg items-stretch">
        {links.map((link) => {
          const active = isActive(pathname, link.href);
          return (
            <li key={link.href} className="flex-1">
              <Link
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-14 flex-col items-center justify-center gap-1 px-1 py-2 text-[0.6875rem] font-medium transition-colors",
                  active ? "text-primary" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <link.icon className="size-5" aria-hidden />
                <span className="truncate">{link.shortLabel ?? link.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
