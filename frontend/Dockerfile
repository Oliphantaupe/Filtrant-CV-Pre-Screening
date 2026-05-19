FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM node:20-alpine
RUN npm install -g serve
COPY --from=builder /app/dist /dist
EXPOSE 3000
CMD ["serve", "-s", "/dist"]
