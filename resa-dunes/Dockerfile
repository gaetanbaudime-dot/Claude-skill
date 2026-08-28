# Déploiement Railway / tout hébergeur Docker.
# La base SQLite vit dans /data : monter un volume persistant dessus (Railway : Volume → /data).
FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev || npm install --omit=dev
COPY . .
ENV NODE_ENV=production
ENV DATA_DIR=/data
EXPOSE 3000
CMD ["node", "server.js"]
