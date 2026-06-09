FROM node:22-alpine AS build

WORKDIR /app
ARG VITE_LOGIN_EYEBROW
ENV VITE_LOGIN_EYEBROW=$VITE_LOGIN_EYEBROW
COPY package.json ./
RUN npm install
COPY index.html vite.config.ts tsconfig.json ./
COPY src ./src
RUN test -n "$VITE_LOGIN_EYEBROW"
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
