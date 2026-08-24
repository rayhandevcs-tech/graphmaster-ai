import { api } from "./client";
import type { AvatarOut, AvatarSelectRequest, AvatarWithLock, UserProfile } from "@/types/api";

export const avatarsApi = {
  /**
   * The caller's own catalogue: their gender's avatars, each marked locked or
   * unlocked against their level. `/avatars/all` is the unfiltered catalogue,
   * which is what an administrator's management screen needs.
   */
  forMe: () => api.get<AvatarWithLock[]>("/avatars"),

  all: () => api.get<AvatarOut[]>("/avatars/all"),

  select: (payload: AvatarSelectRequest) => api.put<UserProfile>("/avatars/select", payload),
};
