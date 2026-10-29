FROM python:3.12-slim

# Dépendances système minimales et gestion du fuseau horaire
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Création d'un utilisateur non-root dédié (SEC-13)
RUN groupadd -g 1000 cemantix && \
    useradd -u 1000 -g cemantix -m -s /bin/sh cemantix

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Copie du code source avec permissions pour l'utilisateur cemantix
COPY --chown=cemantix:cemantix cemantix_rag.py .
COPY --chown=cemantix:cemantix src/ ./src/
COPY --chown=cemantix:cemantix scripts/ ./scripts/
COPY --chown=cemantix:cemantix cemantix_data/lexique_fr.txt ./cemantix_data/lexique_fr.txt

USER cemantix

# Variables d'environnement configurables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ="Europe/Paris"
ENV LM_API="http://host.docker.internal:1234/v1"
ENV LLM_MODEL="qwen3.5-9b-claude-4.6-opus-reasoning-distilled-v2"

# Surveillance de l'état de santé du conteneur (HEALTHCHECK)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python cemantix_rag.py --healthcheck || exit 1

# Point d'entrée (par défaut : menu interactif ou commande injectée par compose)
ENTRYPOINT ["python", "cemantix_rag.py"]
CMD []
