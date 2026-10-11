FROM node:24-slim AS build
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
RUN corepack enable
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml /app/apps/web/
WORKDIR /app/apps/web
RUN pnpm install --frozen-lockfile
WORKDIR /app
COPY apps/web /app/apps/web
COPY packages /app/packages
RUN cd apps/web && pnpm build

FROM node:24-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /app/apps/web/.next/standalone /app
COPY --from=build --chown=node:node /app/apps/web/.next/static /app/apps/web/.next/static
COPY --from=build --chown=node:node /app/apps/web/public /app/apps/web/public
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
