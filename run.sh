#!/bin/bash
# Redemarrage sur de l'app : verifie le code, lance la suite de tests,
# interrompt en cas d'echec (reste sur la derniere version stable), sinon
# recharge UNIQUEMENT le process uwsgi de cette app.
#
# Ne jamais utiliser `service uwsgi <action> <app>` ni
# `systemctl <action> uwsgi <app>` : les arguments supplementaires sont
# ignores et tout uwsgi est arrete/redemarre (vecu le 10 septembre 2026,
# ~28s de coupure totale sur toutes les apps -- voir OPERATIONS.md,
# regle de securite n6, et NOTES-evolutions.md).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="$(basename "$APP_DIR")"
PIDFILE="/run/uwsgi/app/${APP_NAME}/pid"

echo "==> Verification du code (py_compile)"
find "$APP_DIR" -name "*.py" -not -path "*/tests/*" -print0 \
    | xargs -0 python3 -m py_compile

echo "==> Suite de tests"
if ! "${APP_DIR}/run_tests.sh"; then
    echo "!! Tests en echec : redemarrage annule, l'app ${APP_NAME} en cours reste active." >&2
    exit 1
fi

if [ ! -f "$PIDFILE" ]; then
    echo "!! Pidfile introuvable (${PIDFILE}) : l'app ${APP_NAME} tourne-t-elle ?" >&2
    exit 1
fi

echo "==> Rechargement cible de ${APP_NAME} (kill -HUP, jamais 'service uwsgi ...')"
sudo kill -HUP "$(cat "$PIDFILE")"
echo "==> OK"
