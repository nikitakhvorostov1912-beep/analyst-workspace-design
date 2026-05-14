# Production-ready Next.js 15 dev/prod image
FROM node:22-alpine

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10 --activate

# Сначала только манифесты — кэш слоя зависимостей
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

# Затем исходники
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3010
ENV HOSTNAME=0.0.0.0

EXPOSE 3010

# В docker-compose dev-режим: hot reload + быстрый ребилд
CMD ["pnpm", "dev", "--", "-p", "3010", "-H", "0.0.0.0"]
