# ---------- DEV (hot reload) ----------
FROM node:20-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
# vite needs 0.0.0.0 host
CMD ["npm","run","dev","--","--host","0.0.0.0"]

# ---------- PROD build ----------
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

# ---------- PROD serve ----------
FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
# small nginx tweak so client-side routing works:
RUN printf 'server { \n\
  listen 80; \n\
  server_name _; \n\
  root /usr/share/nginx/html; \n\
  location / { try_files $uri /index.html; } \n\
  sendfile on; \n\
}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx","-g","daemon off;"]
