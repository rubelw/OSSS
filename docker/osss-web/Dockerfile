# Option B: Dev-friendly bind mount + runtime npm install
FROM node:20-alpine

# Work inside /app
WORKDIR /app

# Environment for reliable file watching
ENV NODE_ENV=development \
    CHOKIDAR_USEPOLLING=true \
    WATCHPACK_POLLING=true

EXPOSE 3000

# At runtime we will:
#  1. npm install  (into /app/node_modules which is a named volume)
#  2. start next dev
CMD ["sh", "-c", "npm install && npm run dev -- --port 3000"]
