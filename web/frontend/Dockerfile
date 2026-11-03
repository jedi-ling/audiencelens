FROM node:22-slim AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# VITE_* 是构建期变量：vite build 把它内联进产出的 JS，运行时改 .env 不生效，
# 必须在这一步之前就注入。ARG 默认给 zh——不传 build arg 时退回纯中文，
# 语言切换器不出现，不会半成品上线。
ARG VITE_AL_LOCALES=zh
ENV VITE_AL_LOCALES=$VITE_AL_LOCALES
# ICP 备案号（只有在中国大陆提供服务的实例才需要）。不传就不显示，见 src/lib/site.ts
ARG VITE_ICP_TEXT=
ENV VITE_ICP_TEXT=$VITE_ICP_TEXT
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
