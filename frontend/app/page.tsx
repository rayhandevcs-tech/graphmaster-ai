import Link from "next/link";
import { BarChart3, PenLine, Trophy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * The landing page — a Server Component with no client JavaScript of its own,
 * which is what keeps a first visit cheap (06-frontend-architecture §3).
 */
export default function LandingPage() {
  return (
    <div className="flex flex-col gap-16 py-8">
      <section className="mx-auto flex max-w-3xl flex-col items-center gap-6 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-balance sm:text-5xl">
          Describe the graph. <span className="text-primary">Earn the crown.</span>
        </h1>
        <p className="text-muted-foreground max-w-2xl text-lg text-pretty">
          GraphMaster marks your academic writing on the vocabulary you actually used — typed or
          handwritten — and turns practice into levels, streaks and rewards.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/register">Create an account</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>
      </section>

      <section aria-labelledby="how" className="mx-auto w-full max-w-5xl">
        <h2 id="how" className="sr-only">
          How it works
        </h2>
        <div className="grid gap-6 sm:grid-cols-3">
          <Feature
            Icon={BarChart3}
            title="Read a real chart"
            body="Line, bar, pie and area charts drawn from structured data — crisp at any size, and readable as a table."
          />
          <Feature
            Icon={PenLine}
            title="Write it your way"
            body="Type your description, or photograph a handwritten page and check what was read before it is marked."
          />
          <Feature
            Icon={Trophy}
            title="See what you missed"
            // Deliberately no percentage: the weights are deployment configuration
            // and `/analysis/rubric` — which publishes them — needs a token, so a
            // number written here could not be corrected when a study retunes it.
            body="Most of the score is the vocabulary a description needs. The words you did not reach for are the lesson."
          />
        </div>
      </section>
    </div>
  );
}

function Feature({ Icon, title, body }: { Icon: typeof BarChart3; title: string; body: string }) {
  return (
    <Card>
      <CardHeader>
        <Icon className="text-primary size-6" aria-hidden />
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <CardDescription>{body}</CardDescription>
      </CardContent>
    </Card>
  );
}
