# The viewer. Built as a Next standalone bundle so the runtime image carries neither
# pnpm nor the dependency tree.
FROM node:22-slim AS deps
RUN corepack enable
WORKDIR /app
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml web/.npmrc ./
RUN pnpm install --frozen-lockfile


FROM node:22-slim AS build
RUN corepack enable
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY web/ ./
# Baked into the bundle at build time, so the browser's own requests stay same-origin
# and the value here only decides where the server-side proxy sends them.
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build


FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
