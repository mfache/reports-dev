#!/bin/bash
# Execute la suite de tests avec les memes droits que le process uwsgi
# reel (necessaire pour lire /etc/boitier-fleet/db*.env, illisible en
# dehors du groupe mariadb). Voir tests/README.md.
#
# Le venv utilise est deduit du nom de ce dossier : reports-dev ici,
# reports une fois ce checkout promu en production (meme convention que
# les fichiers uwsgi existants : /opt/venv/<nom-du-dossier>).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="$(basename "$APP_DIR")"
VENV_DIR="/opt/venv/${APP_NAME}"

if [ ! -x "${VENV_DIR}/bin/python3" ]; then
    echo "!! venv introuvable : ${VENV_DIR}" >&2
    exit 1
fi

# -p no:cacheprovider : le process tourne en mariadb, le checkout
# appartient a marc/root, pas de cache inter-executions inscriptible
# (et pas necessaire pour une suite aussi rapide).
exec sudo -u mariadb env \
    PYTHONPATH="${APP_DIR}:${APP_DIR}/src" \
    "${VENV_DIR}/bin/python3" -m pytest -p no:cacheprovider "${APP_DIR}/tests" "$@"
