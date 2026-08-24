import { api } from "./client";
import type {
  AuthResponse,
  ChangePasswordRequest,
  LoginRequest,
  MessageResponse,
  PasswordResetConfirm,
  PasswordResetRequest,
  RegisterRequest,
  TokenPair,
} from "@/types/api";

/**
 * Registration and login are `auth: false`: they are how a token comes into
 * existence, so a 401 from either is the answer to the request, not a stale
 * credential to refresh.
 *
 * Both also set the HttpOnly refresh cookie, which is why the client sends
 * `credentials: "include"` on everything.
 */
export const authApi = {
  register: (payload: RegisterRequest) =>
    api.post<AuthResponse>("/auth/register", payload, { auth: false }),

  login: (payload: LoginRequest) => api.post<AuthResponse>("/auth/login", payload, { auth: false }),

  /** Rotates the refresh cookie. `AuthProvider` and the client's 401 retry own this. */
  refresh: () => api.post<TokenPair>("/auth/refresh", undefined, { auth: false }),

  /** Deliberately unauthenticated server-side, so an expired token cannot trap a session open. */
  logout: () => api.post<MessageResponse>("/auth/logout", undefined, { auth: false }),

  logoutEverywhere: () => api.post<MessageResponse>("/auth/logout-all"),

  changePassword: (payload: ChangePasswordRequest) =>
    api.post<MessageResponse>("/auth/change-password", payload),

  requestPasswordReset: (payload: PasswordResetRequest) =>
    api.post<MessageResponse>("/auth/password-reset/request", payload, { auth: false }),

  confirmPasswordReset: (payload: PasswordResetConfirm) =>
    api.post<MessageResponse>("/auth/password-reset/confirm", payload, { auth: false }),
};
