import Link from "next/link";
import { Hammer } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * A route that exists, is guarded, and is not built yet.
 *
 * Every link in the navigation points somewhere real from sprint 10 onwards —
 * a 404 from the app's own menu reads as a broken deployment, not as an
 * unfinished one. Each of these is replaced by the sprint named on it.
 */
export function ComingSoon({
  title,
  sprint,
  children,
  backHref = "/dashboard",
  backLabel = "Back to your dashboard",
}: {
  title: string;
  sprint: string;
  children: React.ReactNode;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <Badge variant="muted">{sprint}</Badge>
      </div>
      <Card>
        <CardHeader>
          <Hammer className="text-muted-foreground size-6" aria-hidden />
          <CardTitle>Being built</CardTitle>
          <CardDescription>{children}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline">
            <Link href={backHref}>{backLabel}</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
