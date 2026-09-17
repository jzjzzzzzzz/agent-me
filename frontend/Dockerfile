FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build
FROM nginx:1.31-alpine@sha256:c8497b180665e631ec92a5091125bec5b214f0e2b99409e30653a125b37557da
COPY --from=build /app/dist /usr/share/nginx/html
COPY security-headers.conf /etc/nginx/agent-me-security-headers.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
