# UPI settlement console: static dashboard served by nginx, which proxies /api/ to settlement-backend:5000.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY public/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1/healthz || exit 1
