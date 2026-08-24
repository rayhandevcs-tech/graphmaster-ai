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
