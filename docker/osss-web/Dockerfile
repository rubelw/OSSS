# Use official Node.js LTS Alpine base
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json package-lock.json* ./
RUN npm install

# At runtime the source code will be bind-mounted from host
# so we don't COPY it here to keep dev iterations fast.

# Environment defaults (can be overridden in docker-compose.yml)
ENV NODE_ENV=development \
    CHOKIDAR_USEPOLLING=true \
    WATCHPACK_POLLING=true

EXPOSE 3000

# Default command: run Next.js dev server
CMD ["npm", "run", "dev", "--", "--port", "3000"]
