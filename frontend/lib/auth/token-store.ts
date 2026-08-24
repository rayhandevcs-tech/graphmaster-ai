/**
 * Where the access token lives: in memory, in the browser, and nowhere else.
 *
 * Not `localStorage` and not a readable cookie. Both are readable by any
 * script on the page, which turns one XSS bug into a stolen 30-minute token;
 * a module variable dies with the tab. The cost is that a hard refresh starts
 * with no token — which is what `AuthProvider`'s bootstrap refresh is for.
 *
 * The API client reads it from here rather than from React context because the
 * client is a plain module: making it a hook would mean every call site became
 * a component.
 */

type Listener = (token: string | null) => void;

let accessToken: string | null = null;
const listeners = new Set<Listener>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  if (typeof window === "undefined") {
    // Module state on the server is shared by every request the process
    // handles, so a token stored here would leak between users. Nothing
    // legitimately writes one during server rendering; failing loudly beats
    // discovering this from a bug report.
    throw new Error("The access token may only be set in the browser.");
  }
  if (accessToken === token) return;
  accessToken = token;
  for (const listener of listeners) listener(token);
}

/** Returns an unsubscribe function. */
export function subscribeToAccessToken(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Test seam: drops the token and every listener. */
export function resetTokenStore(): void {
  accessToken = null;
  listeners.clear();
}
