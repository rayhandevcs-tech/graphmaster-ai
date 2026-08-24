import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md flex-col items-center justify-center gap-4 text-center">
      <p className="text-muted-foreground text-sm font-medium">404</p>
      <h1 className="text-2xl font-semibold tracking-tight">That page does not exist</h1>
      <p className="text-muted-foreground text-sm">
        The link may be out of date, or the page may have moved.
      </p>
      <Button asChild variant="outline">
        <Link href="/">Back to the start</Link>
      </Button>
    </div>
  );
}
