# ── Dependencies ─────────────────────────────────────────────────────────────
FROM node:22-alpine AS deps

WORKDIR /app

# Only the manifests, so this layer is cached until a dependency actually
# changes — the source changes on every commit and would otherwise reinstall
# 470 packages each time.
COPY package.json package-lock.json ./
RUN npm ci


# ── Builder ──────────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# `NEXT_PUBLIC_*` is inlined into the client bundle at build time, not read
# from the environment at runtime: the browser has no `process.env`. Passing
# this only as a runtime variable is the classic way to ship an image that
# talks to localhost from every user's machine.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build


# ── Runtime ──────────────────────────────────────────────────────────────────
FROM node:22-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

# Run unprivileged, matching the API image.
RUN addgroup -g 1001 -S graphmaster && adduser -u 1001 -S graphmaster -G graphmaster

# `output: "standalone"` traces the modules the server actually reaches and
# copies them into `.next/standalone`, so the runtime image carries a server
# and its dependencies rather than the whole `node_modules` tree.
COPY --from=builder --chown=graphmaster:graphmaster /app/.next/standalone ./
COPY --from=builder --chown=graphmaster:graphmaster /app/.next/static ./.next/static
COPY --from=builder --chown=graphmaster:graphmaster /app/public ./public

USER graphmaster

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
