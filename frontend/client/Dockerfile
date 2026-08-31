FROM node:20-slim AS build

WORKDIR /app/client

COPY client/package*.json ./
RUN npm ci

COPY client/index.html ./
COPY client/tsconfig.json ./
COPY client/tsconfig.node.json ./
COPY client/vite.config.ts ./
COPY client/src ./src

RUN npm run build

FROM nginx:1.27-alpine

COPY client/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/client/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
