# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# OpsPortal frontend - Vite build served by nginx, which also fronts the API
# so the whole stack is reachable on a single origin (http://localhost:8080).
# ---------------------------------------------------------------------------

# -- build stage ------------------------------------------------------------
FROM node:26-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .

# Empty base URLs => same-origin requests, which nginx proxies to the backend.
ENV VITE_API_BASE_URL="" \
    VITE_DJANGO_BASE_URL=""

RUN npm run build

# -- runtime stage ----------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

RUN rm /etc/nginx/conf.d/default.conf
# Only *.conf is auto-included by nginx.conf, so the shared proxy headers are
# given an .inc extension and pulled in explicitly by each location block.
COPY nginx.conf /etc/nginx/conf.d/opsportal.conf
COPY nginx-proxy.inc /etc/nginx/conf.d/opsportal_proxy.inc
COPY --from=build /app/dist /usr/share/nginx/html

# The backend writes uploaded media into the shared volume and nginx serves it
# directly from here in production-style runs.
VOLUME ["/usr/share/nginx/media"]

EXPOSE 80

# Use 127.0.0.1, not localhost: busybox wget tries ::1 first and nginx would
# refuse it unless it is also listening on IPv6.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
