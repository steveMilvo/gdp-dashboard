FROM nginx:alpine

COPY . /usr/share/nginx/html

# Write the nginx config as a template. nginx:alpine's entrypoint runs
# envsubst on /etc/nginx/templates/*.template at container start, so
# ${PORT} gets filled in from Railway's env (defaults to 80 elsewhere).
RUN printf '%s\n' \
  'server {' \
  '  listen ${PORT} default_server;' \
  '  root /usr/share/nginx/html;' \
  '  index index.html;' \
  '  gzip on;' \
  '  gzip_types text/plain text/css application/javascript application/json image/svg+xml;' \
  '  location = /locations.json {' \
  '    add_header Cache-Control "no-store";' \
  '    types { } default_type application/json;' \
  '  }' \
  '  location ~* \\.(jpg|jpeg|png|gif|webp|svg|woff2)$ {' \
  '    expires 30d;' \
  '    add_header Cache-Control "public, max-age=2592000";' \
  '  }' \
  '}' > /etc/nginx/templates/default.conf.template \
  && rm -f /etc/nginx/conf.d/default.conf

ENV PORT=80
EXPOSE 80
