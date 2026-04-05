FROM node:20-slim AS build

WORKDIR /app/admin

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY admin/package*.json ./
RUN npm install

COPY admin/index.html ./
COPY admin/tsconfig.json ./
COPY admin/tsconfig.node.json ./
COPY admin/vite.config.ts ./
COPY admin/src ./src
COPY shared ../shared

RUN npm run build

FROM nginx:1.27-alpine

COPY admin/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/admin/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
