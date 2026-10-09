FROM node:24-bookworm-slim
WORKDIR /app
COPY community/api.mjs community/api.mjs
COPY community/oracle/server.mjs community/oracle/server.mjs
COPY migrations/0001_community.sql migrations/0001_community.sql
RUN mkdir -p /var/lib/knua && chown node:node /var/lib/knua
USER node
ENV HOST=0.0.0.0 PORT=8080 KNUA_DATABASE_PATH=/var/lib/knua/community.sqlite
CMD ["node", "community/oracle/server.mjs"]
