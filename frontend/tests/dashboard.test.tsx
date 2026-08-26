/**
 * The student's home screen, where the encouraging framing can quietly become
 * a claim the data does not support.
 *
 * These cover the four places that happens: a zero standing in for a mark that
 * was never given, the lowest tier acquiring a losing name once it is put in a
 * list beside the others, a broken streak reported as a loss rather than as a
 * way back, and the recent-work list becoming a table of numbers with nothing
 * to open.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AchievementStrip } from "@/components/dashboard/achievement-strip";
import { StatTiles } from "@/components/dashboard/stat-tiles";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { StreakFlame } from "@/components/gamification/streak-flame";
import { TierDistribution } from "@/components/gamification/tier-distribution";
import type { StudentDashboard } from "@/types/api";

function dashboard(overrides: Partial<StudentDashboard> = {}): StudentDashboard {
  return {
    total_attempts: 6,
    average_score: 68.4,
    highest_score: 81,
    average_vocabulary_percentage: 62.5,
    reward_tier_distribution: { crown: 1, flower: 3, steady: 1, hammer: 1 },
    total_xp: 940,
    current_level: 3,
    xp_into_level: 40,
    xp_for_next_level: 150,
    level_progress_percent: 26.7,
    current_streak_days: 4,
    longest_streak_days: 9,
    achievements: [],
    badges: [],
    recent_activity: [],
    score_trend: [],
    ...overrides,
  };
}

describe("the headline figures", () => {
  it("shows an em dash rather than a zero before anything has been marked", () => {
    render(
      <StatTiles
        dashboard={dashboard({
          total_attempts: 0,
          average_score: 0,
          highest_score: 0,
          average_vocabulary_percentage: 0,
        })}
      />,
    );

    // The attempt count is genuinely zero. The three averages do not exist —
    // and "0.0%" is a mark a student would believe they had been given.
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
  });

  it("shows the real figures once there is work behind them", () => {
    render(<StatTiles dashboard={dashboard()} />);

    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("68.4%")).toBeInTheDocument();
    expect(screen.getByText("81.0%")).toBeInTheDocument();
    expect(screen.getByText("62.5%")).toBeInTheDocument();
  });
});

describe("the spread of results", () => {
  it("names every tier, so the bar is never the only signal", () => {
    render(<TierDistribution distribution={{ crown: 1, flower: 3, steady: 1, hammer: 1 }} />);

    for (const label of ["Crown tier", "Flower tier", "Steady tier", "Practice tier"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("never calls the lowest tier a failure (FR-7.7)", () => {
    const { container } = render(
      <TierDistribution distribution={{ crown: 0, flower: 0, steady: 0, hammer: 5 }} />,
    );

    const text = container.textContent ?? "";
    for (const word of ["hammer", "fail", "poor", "weak", "bad", "worst"]) {
      expect(text.toLowerCase()).not.toContain(word);
    }
  });

  it("says what will fill it rather than drawing an empty bar", () => {
    render(<TierDistribution distribution={{}} />);
    expect(screen.getByText(/first marked description/i)).toBeInTheDocument();
  });
});

describe("the practice streak", () => {
  it("offers the way back instead of reporting the loss", () => {
    const { container } = render(<StreakFlame currentDays={0} longestDays={9} />);

    expect(screen.getByText(/no streak yet/i)).toBeInTheDocument();
    // Their best is still theirs, and saying so is not the same as saying they
    // lost it.
    expect(screen.getByText(/best is 9 days/i)).toBeInTheDocument();
    expect((container.textContent ?? "").toLowerCase()).not.toMatch(/lost|broke|failed/);
  });

  it("counts a running streak in whole days, singular included", () => {
    const { rerender } = render(<StreakFlame currentDays={1} longestDays={1} />);
    expect(screen.getByText(/1 day in a row/i)).toBeInTheDocument();

    rerender(<StreakFlame currentDays={4} longestDays={9} />);
    expect(screen.getByText(/4 days in a row/i)).toBeInTheDocument();
  });
});

describe("recent work", () => {
  const item = {
    submission_id: "8f2a1b4c-0000-4000-8000-000000000001",
    graph_title: "Renewable energy in four countries",
    graph_type: "bar" as const,
    final_score: 74.2,
    vocabulary_percentage: 71,
    reward_tier: "flower" as const,
    scored_at: new Date().toISOString(),
  };

  it("makes every row a way into the full result", () => {
    render(<RecentActivity items={[item]} />);

    const link = screen.getByRole("link", { name: /renewable energy/i });
    expect(link).toHaveAttribute("href", `/submissions/${item.submission_id}`);
    expect(within(link).getByText("74%")).toBeInTheDocument();
  });

  it("explains an empty list and offers the action that fills it", () => {
    render(<RecentActivity items={[]} />);

    expect(screen.getByText(/no marked work yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /choose a graph/i })).toHaveAttribute(
      "href",
      "/practice",
    );
  });
});

describe("the achievement strip's empty state", () => {
  it("invites a student who has not started", () => {
    render(<AchievementStrip achievements={[]} attempts={0} />);

    expect(screen.getByText("Your first one is close")).toBeInTheDocument();
    expect(screen.getByText(/Finishing a single description unlocks one/)).toBeInTheDocument();
  });

  it("never tells a student who has practised that one description would do it", () => {
    // Shown to a student with nine marked descriptions, both halves of that
    // sentence were false. The wording comes from practice history now.
    render(<AchievementStrip achievements={[]} attempts={9} />);

    expect(
      screen.queryByText(/Finishing a single description unlocks one/),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Your first one is close")).not.toBeInTheDocument();
    expect(screen.getByText(/take more than one description/i)).toBeInTheDocument();
  });
});
