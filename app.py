#!/usr/bin/python3
"""Point d'entree WSGI pour l'API de flotte reports (routes definies dans
api.py). Expose 'application', attendu par la configuration uWSGI
(/etc/uwsgi/apps-enabled/reports.ini : module = app:application).

Monte sous /reports/api car nginx transmet le chemin complet sans le
tronquer (verifie le 9 septembre 2026 apres restauration suite a un
ecrasement accidentel de ce fichier par la copie de headscale-admin/app.py).

10 septembre 2026 : ajout du montage de l'UI (ui_app, routes definies dans
ui.py) sous /reports. Absent depuis la reconstruction du 9 septembre :
seule l'API repondait, l'UI renvoyait un 404 une fois l'authentification
passee (jamais remarque faute de test de bout en bout a l'epoque).
"""

from bottle import Bottle

from api import api_app
from ui import ui_app

application = Bottle()
application.mount('/reports/api', api_app)
application.mount('/reports', ui_app)
