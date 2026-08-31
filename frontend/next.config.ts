import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  // A self-contained server bundle, so the production image copies a build
  // output rather than a `node_modules` tree (see Dockerfile).
  output: "standalone",

  typescript: {
    // The default already fails the build on a type error; stated explicitly
    // because silencing it is a one-line change someone might make under
    // deadline, and this is the only thing enforcing `strict` in CI.
    ignoreBuildErrors: false,
  },

  /**
   * Forward `/api/*` to the backend, server-side.
   *
   * Only when `BACKEND_ORIGIN` is set, which is a deployment where the API
   * lives on a different host — `*.vercel.app` and `*.onrender.com` are
   * different *sites*, so a browser refuses to store the refresh cookie the
   * API sets and the session dies on the next reload. Routed through here the
   * browser only ever talks to its own origin and the cookie is first-party.
   *
   * Unset locally and in any deployment that puts both halves on sub-domains
   * of one registered domain, where the cookie is already first-party and the
   * extra hop would be pure latency.
   *
   * Trade-off: request bodies pass through Vercel, which caps them at about
   * 4.5 MB on the free plan. Handwriting photographs can exceed that; typed
   * submissions and everything else are far below it.
   */
  async rewrites() {
    const backend = process.env.BACKEND_ORIGIN;
    if (!backend) return [];
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // The API sets its own; these cover the documents the browser loads
          // from Next itself. CSP is deliberately absent until sprint 14 can
          // measure it against the real asset set — a wrong CSP fails closed
          // and takes the whole app with it.
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-DNS-Prefetch-Control", value: "off" },
        ],
      },
    ];
  },
};

export default nextConfig;
