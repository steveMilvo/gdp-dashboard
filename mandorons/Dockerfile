FROM nginx:alpine

COPY . /usr/share/nginx/html

# Cache busting + correct mime for the weekly-updated JSON.
# Everything else (HTML, CSS, JS, images) uses nginx defaults.
RUN printf '%s\n' \
  'server {' \
  '  listen 80 default_server;' \
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
  '}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
