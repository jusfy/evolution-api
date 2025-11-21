# =========================
# 1) BUILDER
# =========================
FROM node:20-slim AS builder

# Deixar o npm mais resistente / menos chato com SSL
ENV npm_config_strict_ssl=false
ENV npm_config_registry=https://registry.npmjs.org/
ENV npm_config_fetch_retries=5
ENV npm_config_fetch_retry_mintimeout=20000
ENV npm_config_fetch_retry_maxtimeout=120000

# Dependências básicas pra build
RUN apt-get update && \
    apt-get install -y git wget curl bash openssl dos2unix && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /evolution

# Copia arquivos de dependência
COPY ./package*.json ./
COPY ./tsconfig.json ./
COPY ./tsup.config.ts ./

# Instala dependências
RUN npm ci

# Copia o restante do código
COPY ./src ./src
COPY ./public ./public
COPY ./prisma ./prisma
COPY ./manager ./manager
COPY ./.env.example ./.env
COPY ./runWithProvider.js ./
COPY ./Docker ./Docker

# Ajusta scripts e gera prisma client
RUN chmod +x ./Docker/scripts/* && dos2unix ./Docker/scripts/*

RUN ./Docker/scripts/generate_database.sh

# Build TS → dist
RUN npm run build

# =========================
# 2) FINAL
# =========================
FROM node:20-slim AS final

RUN apt-get update && \
    apt-get install -y tzdata ffmpeg bash openssl && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=America/Sao_Paulo
ENV DOCKER_ENV=true

WORKDIR /evolution

COPY --from=builder /evolution/package.json ./package.json
COPY --from=builder /evolution/package-lock.json ./package-lock.json
COPY --from=builder /evolution/node_modules ./node_modules
COPY --from=builder /evolution/dist ./dist
COPY --from=builder /evolution/prisma ./prisma
COPY --from=builder /evolution/manager ./manager
COPY --from=builder /evolution/public ./public
COPY --from=builder /evolution/.env ./.env
COPY --from=builder /evolution/Docker ./Docker
COPY --from=builder /evolution/runWithProvider.js ./runWithProvider.js
COPY --from=builder /evolution/tsup.config.ts ./tsup.config.ts

EXPOSE 8080

ENTRYPOINT ["/bin/bash", "-c", ". ./Docker/scripts/deploy_database.sh && npm run start:prod" ]
