FROM node:18-alpine

WORKDIR /app
# small package.json to install dependencies
COPY ./package.json package-lock.json* ./
RUN npm ci --production

# copy app & static
COPY ./server.js .
COPY ./public ./public

EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
