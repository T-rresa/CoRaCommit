FROM node:20-slim

ARG VERSION=2.1.0
ARG VCS_REF=unknown
# Optional Debian mirror, e.g. --build-arg APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn
ARG APT_MIRROR=

LABEL org.opencontainers.image.title="CoRaCommit node service" \
      org.opencontainers.image.description="CoRaCommit orchestration API, evaluation worker, and database initializers" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/T-rresa/CoRaCommit" \
      org.opencontainers.image.licenses="MIT"

ENV NODE_ENV=production

WORKDIR /app

RUN if [ -n "${APT_MIRROR}" ]; then \
      for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        [ -f "$f" ] && sed -i "s|http://deb.debian.org|${APT_MIRROR}|g" "$f"; \
      done; \
    fi \
    && apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --chown=node:node . .

# loggerService.js creates /app/logs at startup; the non-root user must own it.
RUN mkdir -p /app/logs && chown -R node:node /app/logs

USER node

EXPOSE 3001

CMD ["npm", "run", "start:api"]