"use client";

/**
 * Who is signed in, for the whole client tree.
 *
 * The access token is held in memory by `token-store`; this context holds the
 * profile that goes with it and the three operations that change it. A hard
 * refresh starts with neither, so the provider bootstraps by asking the API to
 * rotate the refresh cookie — the one credential that survives a reload.
 *
 * This is not a security boundary. Every endpoint demands a token server-side
 * (and the backend's own surface test proves it); what happens here decides
 * what the interface *shows*, which is a different question.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { authApi, usersApi, setUnauthenticatedHandler } from "@/lib/api";
import { getAccessToken, setAccessToken } from "@/lib/auth/token-store";
import type { LoginRequest, RegisterRequest, UserProfile } from "@/types/api";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthContextValue {
  user: UserProfile | null;
  /** `loading` only until the bootstrap refresh settles, once per page load. */
  status: AuthStatus;
  isAuthenticated: boolean;
  signIn: (credentials: LoginRequest) => Promise<UserProfile>;
  register: (payload: RegisterRequest) => Promise<UserProfile>;
  signOut: () => Promise<void>;
  /** Re-reads the profile — XP, level and streak change under the user's feet. */
  reloadUser: () => Promise<UserProfile | null>;
  /** For the screens that already receive a fresh profile in their response. */
  applyUser: (user: UserProfile) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const router = useRouter();
  const queryClient = useQueryClient();

  // Read inside callbacks so the effect below does not re-register on
  // every navigation.
  const routerRef = useRef(router);
  routerRef.current = router;

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
    // Otherwise the next person to sign in on this browser sees the previous
    // student's dashboard for as long as the cache considers it fresh.
    queryClient.clear();
  }, [queryClient]);

  /* The client calls this when a refresh fails for a session that existed —
     expired, revoked, or signed out in another tab. */
  useEffect(() => {
    setUnauthenticatedHandler(() => {
      setUser(null);
      setStatus("anonymous");
      queryClient.clear();
      const here = window.location.pathname + window.location.search;
      const next = here === "/" ? "" : `?next=${encodeURIComponent(here)}`;
      routerRef.current.replace(`/login${next}`);
    });
    return () => setUnauthenticatedHandler(null);
  }, [queryClient]);

  /* Bootstrap. The refresh cookie is HttpOnly, so whether one exists is not a
     question this code can answer — it has to try. A failure here is the
     ordinary case for a visitor who has never signed in, and must not look
     like an error. */
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const tokens = await authApi.refresh();
        if (cancelled) return;
        setAccessToken(tokens.access_token);

        const profile = await usersApi.me();
        if (cancelled) return;
        setUser(profile);
        setStatus("authenticated");
      } catch {
        if (cancelled) return;
        if (getAccessToken() !== null) setAccessToken(null);
        setUser(null);
        setStatus("anonymous");
      }
    })();

    return () => {
      cancelled = true;
    };
    // Once per mount. A re-run would rotate the refresh token again, and the
    // backend treats a reused rotated token as theft.
  }, []);

  const signIn = useCallback(
    async (credentials: LoginRequest) => {
      const { user: profile, tokens } = await authApi.login(credentials);
      setAccessToken(tokens.access_token);
      queryClient.clear();
      setUser(profile);
      setStatus("authenticated");
      return profile;
    },
    [queryClient],
  );

  const register = useCallback(
    async (payload: RegisterRequest) => {
      const { user: profile, tokens } = await authApi.register(payload);
      setAccessToken(tokens.access_token);
      queryClient.clear();
      setUser(profile);
      setStatus("authenticated");
      return profile;
    },
    [queryClient],
  );

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // The server-side session may already be gone. Signing out locally is
      // the part the student asked for, and it must happen either way.
    }
    clearSession();
    router.replace("/login");
  }, [clearSession, router]);

  const reloadUser = useCallback(async () => {
    try {
      const profile = await usersApi.me();
      setUser(profile);
      setStatus("authenticated");
      return profile;
    } catch {
      return null;
    }
  }, []);

  const applyUser = useCallback((profile: UserProfile) => {
    setUser(profile);
    setStatus("authenticated");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      isAuthenticated: status === "authenticated" && user !== null,
      signIn,
      register,
      signOut,
      reloadUser,
      applyUser,
    }),
    [user, status, signIn, register, signOut, reloadUser, applyUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return context;
}
