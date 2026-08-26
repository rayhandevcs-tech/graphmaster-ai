"use client";

import { LineChart } from "lucide-react";

import { ChartPanel } from "@/components/charts/chart-panel";
import { EmptyState } from "@/components/layout/empty-state";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { trendChartData, type ScoreTrendPoint } from "@/lib/charts/trend";

/**
 * Score over the days the student practised.
 *
 * The description under the title is load-bearing, not decoration. The API
 * returns one point per day work was marked and nothing for the days between,
 * so the axis is a sequence of practice days rather than a calendar — and a
 * chart that looks like a calendar but is not would have a student reading a
 * fortnight's gap as an overnight drop. Saying what the axis is costs one line
 * and removes the misreading entirely.
 *
 * A single point is still drawn. It is a dot rather than a line, which is the
 * honest picture of one day's work, and it makes the card feel like it has
 * started rather than like it is broken.
 */
export function TrendCard({ points }: { points: ScoreTrendPoint[] }) {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Your progress</CardTitle>
        <CardDescription>
          {points.length === 0
            ? "Marked descriptions appear here as you complete them."
            : "One point for each day you practised — not every day in between."}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex-1">
        {points.length === 0 ? (
          <EmptyState
            icon={LineChart}
            title="Nothing to plot yet"
            description="Once two or more days of work have been marked, this chart shows whether your scores are moving."
          />
        ) : (
          <ChartPanel
            chartData={trendChartData(points)}
            graphType="line"
            title="Your score over the days you practised"
            height="h-[15rem] sm:h-[18rem]"
          />
        )}
      </CardContent>
    </Card>
  );
}
