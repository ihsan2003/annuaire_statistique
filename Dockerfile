# Utiliser une image Python officielle
FROM python:3.11-slim

# Variables d'environnement pour Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système nécessaires pour MySQL et Node.js
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier des dépendances
COPY requirements.txt /app/

# Installer les dépendances Python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copier le projet Django
COPY . /app/

# Créer les répertoires nécessaires
RUN mkdir -p /app/static /app/media /app/logs

# Compiler Tailwind CSS (si nécessaire)
RUN cd theme/static_src && npm install && cd /app

# Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput || true

# Exposer le port
EXPOSE 8000

# Script de démarrage
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]