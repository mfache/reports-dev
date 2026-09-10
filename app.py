#!/usr/bin/python3
"""Point d'entree WSGI pour l'API de flotte reports (routes assemblees
dans web/api.py, organisees par domaine sous services/). Expose
'application', attendu par la configuration uWSGI
(/etc/uwsgi/apps-enabled/reports.ini : module = app:application).

Monte sous /reports/api car nginx transmet le chemin complet sans le
tronquer (verifie le 9 septembre 2026 apres restauration suite a un
ecrasement accidentel de ce fichier par la copie de headscale-admin/app.py).

10 septembre 2026 : ajout du montage de l'UI (ui_app, routes definies dans
ui.py) sous /reports. Absent depuis la reconstruction du 9 septembre :
seule l'API repondait, l'UI renvoyait un 404 une fois l'authentification
passee (jamais remarque faute de test de bout en bout a l'epoque).

10 septembre 2026 (refonte) : le prefixe de montage est desormais
configurable via la variable d'environnement REPORTS_BASE_PATH, pour
permettre a l'interface de dev (/reports-dev, app uwsgi separee) de
tourner sur le meme code sans jamais repondre sous /reports. Sans cette
variable, le comportement de production est strictement inchange.

10 septembre 2026 (refonte, suite) : api.py (1696 lignes) a ete eclate
en web/api.py (assemblage + routes transverses) et services/*.py
(fleet, chantiers, sync, trends, logs, headscale), sur le modele
rpinode. ui.py (1169 lignes) a suivi le meme principe : web/ui.py garde
l'essentiel des pages, web/stream.py isole les 2 routes SSE, et
services/templates_maintenance.py isole la maintenance des templates
Modbus partages. Voir CAHIER-DES-CHARGES-REFONTE.md.
"""

import os

from bottle import Bottle

from web.api import api_app
from web.ui import ui_app

BASE_PATH = os.environ.get('REPORTS_BASE_PATH', '/reports')

application = Bottle()
application.mount(f'{BASE_PATH}/api', api_app)
application.mount(BASE_PATH, ui_app)
