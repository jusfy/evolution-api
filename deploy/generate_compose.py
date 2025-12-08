#!/usr/bin/env python3
import yaml
import os
from copy import deepcopy

# Diretório do script e raiz do repositório
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

# CONFIGURAÇÕES
BASE_FILE = os.path.join(SCRIPT_DIR, "docker-compose.base.yml")        # seu compose original
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "docker-compose.generated.yml") # arquivo de saída
ENV_FILE = os.path.join(REPO_ROOT, ".env")                             # arquivo .env da raiz
NUM_INSTANCES = 120                           # QUANTAS máquinas evo você quer gerar
PREFIX = "cluster-evo-"                               # prefixo: evo1, evo2, ...

TEMPLATE_SERVICE_NAME = "evolution_api_test"  # serviço template que vamos clonar


def load_env_file(env_path):
    """Carrega variáveis do arquivo .env"""
    env_vars = {}
    if not os.path.exists(env_path):
        print(f"⚠️  Arquivo .env não encontrado em: {env_path}")
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Ignora comentários e linhas vazias
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


def main():
    # Carrega variáveis do .env
    env_vars = load_env_file(ENV_FILE)

    DATABASE_URI = env_vars.get("DATABASE_CONNECTION_URI", "")
    API_KEY = env_vars.get("AUTHENTICATION_API_KEY", "")
    SQS_ACCESS_KEY_ID = env_vars.get("SQS_ACCESS_KEY_ID", "")
    SQS_SECRET_ACCESS_KEY = env_vars.get("SQS_SECRET_ACCESS_KEY", "")
    SQS_ACCOUNT_ID = env_vars.get("SQS_ACCOUNT_ID", "")
    SQS_REGION = env_vars.get("SQS_REGION", "")

    if not DATABASE_URI:
        print("⚠️  DATABASE_CONNECTION_URI não encontrada no .env")
    if not API_KEY:
        print("⚠️  AUTHENTICATION_API_KEY não encontrada no .env")
    if not SQS_ACCESS_KEY_ID:
        print("⚠️  SQS_ACCESS_KEY_ID não encontrada no .env")

    with open(BASE_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    services = data.get("services", {})
    if TEMPLATE_SERVICE_NAME not in services:
        raise SystemExit(f"Service '{TEMPLATE_SERVICE_NAME}' não encontrado em {BASE_FILE}")

    template = services[TEMPLATE_SERVICE_NAME]

    for i in range(1, NUM_INSTANCES + 1):
        client_id = f"{PREFIX}{i}"          # ex: evo1, evo2...
        service_name = f"{PREFIX}_{client_id}"  # ex: evo_evo1 (nome do service no Swarm)

        svc = deepcopy(template)

        # ---------- AJUSTA ENVIRONMENT ----------
        env_list = svc.get("environment", [])
        new_env = []
        for item in env_list:
            if not isinstance(item, str):
                new_env.append(item)
                continue

            if item.startswith("SERVER_URL="):
                new_env.append(f"SERVER_URL=https://{client_id}.evolutionapi.jusfy.dev")
            elif item.startswith("DATABASE_CONNECTION_CLIENT_NAME="):
                new_env.append(f"DATABASE_CONNECTION_CLIENT_NAME={client_id}")
            elif item.startswith("DATABASE_CONNECTION_URI="):
                # Usa valor do .env e adiciona application_name
                if "?" in DATABASE_URI:
                    new_env.append(f"DATABASE_CONNECTION_URI={DATABASE_URI}&application_name={client_id}")
                else:
                    new_env.append(f"DATABASE_CONNECTION_URI={DATABASE_URI}?application_name={client_id}")
            elif item.startswith("AUTHENTICATION_API_KEY="):
                # Usa valor do .env
                new_env.append(f"AUTHENTICATION_API_KEY={API_KEY}")
            elif item.startswith("SQS_ACCESS_KEY_ID="):
                new_env.append(f"SQS_ACCESS_KEY_ID={SQS_ACCESS_KEY_ID}")
            elif item.startswith("SQS_SECRET_ACCESS_KEY="):
                new_env.append(f"SQS_SECRET_ACCESS_KEY={SQS_SECRET_ACCESS_KEY}")
            elif item.startswith("SQS_ACCOUNT_ID="):
                new_env.append(f"SQS_ACCOUNT_ID={SQS_ACCOUNT_ID}")
            elif item.startswith("SQS_REGION="):
                new_env.append(f"SQS_REGION={SQS_REGION}")
            else:
                new_env.append(item)

        svc["environment"] = new_env

        # ---------- AJUSTA LABELS DO TRAEFIK ----------
        deploy = svc.get("deploy", {})
        labels = deploy.get("labels", [])
        new_labels = []
        for l in labels:
            if not isinstance(l, str):
                new_labels.append(l)
                continue

            # troca o nome lógico evolution-test -> evo1 / evo2...
            l = l.replace("evolution-test", client_id)
            # troca host evo-test.evolutionapi... -> evo1.evolutionapi...
            l = l.replace("evo-test.evolutionapi.jusfy.dev", f"{client_id}.evolutionapi.jusfy.dev")
            new_labels.append(l)

        if "deploy" not in svc:
            svc["deploy"] = {}
        svc["deploy"]["labels"] = new_labels

        if "logging" in svc and "options" in svc["logging"]:
            svc["logging"]["options"]["awslogs-stream"] = client_id

        # adiciona o novo service na stack
        services[service_name] = svc

    # se não quiser mais o service de teste original na stack final, remove aqui:
    del services[TEMPLATE_SERVICE_NAME]

    data["services"] = services

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)

    print(f"OK! Gerado {OUTPUT_FILE} com {NUM_INSTANCES} services evo.")


if __name__ == "__main__":
    main()
