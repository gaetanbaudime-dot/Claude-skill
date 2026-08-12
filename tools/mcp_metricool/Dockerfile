# Image volontairement minimale. Deux raisons de ne PAS laisser Nixpacks faire :
#  1. il recopiait les variables du service en ARG/ENV dans l'image, et ces ENV vides
#     écrasaient au démarrage ce que Railway injecte (bug vécu le 12/08 : MCP_TRANSPORT
#     et METRICOOL_TOKEN arrivaient vides alors que l'interface affichait les bonnes
#     valeurs). Aucun ARG ici : les variables ne viennent que de l'environnement d'exécution.
#  2. il tirait 527 Mio d'environnement Nix pour faire tourner un seul fichier Python.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Couche dépendances isolée : rebâtie seulement quand requirements.txt bouge.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY metricool_mcp.py ./

CMD ["python", "metricool_mcp.py"]
