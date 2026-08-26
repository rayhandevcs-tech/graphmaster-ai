/**
 * The board.
 *
 * FR-7.6 is the rule that decides most of this file: what a leaderboard
 * publishes about a student is rank, level and XP, and never a reward tier. A
 * hammer count beside a name in front of the cohort is the humiliation the
 * whole reward design exists to avoid.
 *
 * The other two are structural: the podium's reading order, and a student who
 * is not ranked being invited rather than shown an empty row.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Podium } from "@/components/leaderboard/podium";
import { RankRow } from "@/components/leaderboard/rank-row";
import { YourRank } from "@/components/leaderboard/your-rank";
import type { LeaderboardEntryOut, LeaderboardPosition } from "@/types/api";

function entry(overrides: Partial<LeaderboardEntryOut> = {}): LeaderboardEntryOut {
  return {
    rank: 1,
    user_id: "00000000-0000-0000-0000-000000000001",
    full_name: "Amir Rahman",
    avatar_url: "/avatars/boy-scholar.svg",
    level: 7,
    xp: 1480,
    average_score: 78.2,
    submission_count: 14,
    achievement_count: 5,
    ...overrides,
  };
}

const top3 = [
  entry({ rank: 1, user_id: "a", full_name: "Amir Rahman", xp: 1480 }),
  entry({ rank: 2, user_id: "b", full_name: "Sara Khan", xp: 1240 }),
  entry({ rank: 3, user_id: "c", full_name: "Joy Mensah", xp: 980 }),
];

describe("the podium", () => {
  it("reads first, second, third even though it is drawn second, first, third", () => {
    render(<Podium entries={top3} />);

    const names = screen.getAllByTitle(/Rahman|Khan|Mensah/).map((node) => node.textContent);
    expect(names).toEqual(["Amir Rahman", "Sara Khan", "Joy Mensah"]);
  });

  it("writes each rank out rather than leaving it to the medal colour", () => {
    render(<Podium entries={top3} />);

    expect(screen.getByText("Rank 1")).toBeInTheDocument();
    expect(screen.getByText("Rank 2")).toBeInTheDocument();
    expect(screen.getByText("Rank 3")).toBeInTheDocument();
  });

  it("publishes no reward tier", () => {
    const { container } = render(<Podium entries={top3} />);
    const text = container.textContent ?? "";

    for (const word of ["crown", "flower", "steady", "hammer", "tier", "practice tier"]) {
      expect(text.toLowerCase()).not.toContain(word);
    }
  });

  it("shows nothing rather than a stub when the board is empty", () => {
    const { container } = render(<Podium entries={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("a place on the board", () => {
  it("carries rank, level and XP, and no score", () => {
    render(
      <ul>
        <RankRow entry={entry({ rank: 7, full_name: "Lena Fischer", xp: 870, level: 4 })} />
      </ul>,
    );

    expect(screen.getByText("Rank 7")).toBeInTheDocument();
    expect(screen.getByText("Level 4")).toBeInTheDocument();
    expect(screen.getByText("870")).toBeInTheDocument();
    // The average is on the payload and deliberately not published here.
    expect(screen.queryByText(/78/)).not.toBeInTheDocument();
  });

  it("marks the reader's own row in text as well as in colour", () => {
    render(
      <ul>
        <RankRow entry={entry({ rank: 14, is_you: true })} />
      </ul>,
    );

    expect(screen.getByText(/· you/)).toBeInTheDocument();
  });
});

describe("your own standing", () => {
  const position = (overrides: Partial<LeaderboardPosition> = {}): LeaderboardPosition => ({
    period: {
      scope: "weekly",
      period_start: "2026-08-24",
      period_end: "2026-08-30",
    },
    entry: entry({ rank: 14, xp: 410, level: 6, is_you: true }),
    total_ranked: 88,
    ...overrides,
  });

  it("says how far the next rank is, from the entry above", () => {
    render(<YourRank position={position()} above={entry({ rank: 13, xp: 470 })} />);

    expect(screen.getByText(/60 XP to rank 13/)).toBeInTheDocument();
  });

  it("omits the distance rather than inventing one when nobody is above", () => {
    render(<YourRank position={position()} above={null} />);

    expect(screen.queryByText(/XP to rank/)).not.toBeInTheDocument();
    expect(screen.getByText(/rank 14/)).toBeInTheDocument();
  });

  it("invites an unranked student instead of showing them an empty row", () => {
    render(<YourRank position={position({ entry: null })} above={null} />);

    expect(screen.getByText(/not on this board yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /practise/i })).toBeInTheDocument();
    // Never a zero rank, and never a zero XP presented as a standing.
    expect(screen.queryByText(/rank 0/i)).not.toBeInTheDocument();
  });
});
