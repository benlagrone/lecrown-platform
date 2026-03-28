FROM node:20-slim

WORKDIR /app/admin

COPY admin/package.json ./
RUN npm install

COPY admin/index.html ./
COPY admin/tsconfig.json ./
COPY admin/tsconfig.node.json ./
COPY admin/vite.config.ts ./
COPY admin/src ./src
COPY shared ../shared

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
