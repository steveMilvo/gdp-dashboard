FROM node:20-alpine

WORKDIR /app

# Install only production deps. package-lock.json is committed so this is reproducible.
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --no-audit --no-fund || npm install --omit=dev --no-audit --no-fund

# Copy the rest of the site (Dockerfile/.dockerignore/previews etc are excluded
# via .dockerignore so they don't ship to the container).
COPY . ./

ENV NODE_ENV=production
# Railway injects $PORT (usually 8080). Fallback to 3000 for local dev.
ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
