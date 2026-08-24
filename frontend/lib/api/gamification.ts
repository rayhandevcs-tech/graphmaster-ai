import { api, type PageParams } from "./client";
import type {
  AchievementOut,
  BadgeOut,
  LevelOut,
  PageXPEventOut,
  XPAdjustment,
  XPEventOut,
} from "@/types/api";

export const gamificationApi = {
  /** Unlocked and locked alike, with progress — a visible distance is what motivates. */
  achievements: () => api.get<AchievementOut[]>("/gamification/achievements"),

  badges: () => api.get<BadgeOut[]>("/gamification/badges"),

  level: () => api.get<LevelOut>("/gamification/level"),

  /** The XP ledger, newest first. Append-only: corrections are offsetting entries. */
  xpHistory: (params: PageParams = {}) =>
    api.get<PageXPEventOut>("/gamification/xp-history", { query: { ...params } }),

  /** Administrators only. Writes an offsetting entry; it never edits history. */
  adjustXp: (payload: XPAdjustment) => api.post<XPEventOut>("/gamification/adjustments", payload),
};
