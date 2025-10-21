#!/bin/bash

# Attendre que la base de données soit prête
echo "En attente de la base de données..."
while ! nc -z db 3306; do
  sleep 0.5
done
echo "Base de données prête!"

# Appliquer les migrations
echo "Application des migrations..."
python manage.py makemigrations
python manage.py migrate

# Créer un superutilisateur si besoin (optionnel)
# python manage.py createsuperuser --noinput || true

# Collecter les fichiers statiques
echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

# Démarrer le serveur
echo "Démarrage du serveur Django..."
exec "$@"