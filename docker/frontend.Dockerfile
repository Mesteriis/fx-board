FROM node:22-slim AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend .
RUN npm run build

FROM node:22-slim

ENV HOST=0.0.0.0 \
    PORT=3000

WORKDIR /app

COPY --from=build /app/.output ./.output

CMD ["node", ".output/server/index.mjs"]
