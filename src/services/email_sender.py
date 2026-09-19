"""Envoi d'emails via le relais SMTP existant (Office 365 / ssmtp),
reutilise pour les invitations a l'application mobile (voir
services/mobile.py et web/admin_users.py). Configuration lue depuis les
memes fichiers d'environnement que la base de donnees (SMTP_HOST,
SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM dans
/etc/boitier-fleet/db.env ou db-dev.env, voir core/config.py).
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from core.config import _ENV


class EmailConfigError(RuntimeError):
    """Configuration SMTP absente ou incomplete."""


class EmailSendError(RuntimeError):
    """Echec de l'envoi (authentification, connexion, etc.)."""


def send_email(to_address, subject, body_text):
    """Envoie un email texte simple. Leve EmailConfigError ou
    EmailSendError en cas de probleme (jamais silencieux : l'appelant
    doit decider quoi afficher a l'admin)."""
    host = _ENV.get("SMTP_HOST", "")
    port_raw = _ENV.get("SMTP_PORT", "587")
    user = _ENV.get("SMTP_USER", "")
    password = _ENV.get("SMTP_PASSWORD", "")
    sender = _ENV.get("SMTP_FROM", user)

    if not host or not user or not password:
        raise EmailConfigError(
            "Configuration SMTP incomplete (SMTP_HOST/SMTP_USER/SMTP_PASSWORD)."
        )

    try:
        port = int(port_raw)
    except ValueError:
        port = 587

    msg = MIMEText(body_text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_address

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, [to_address], msg.as_string())
    except smtplib.SMTPException as exc:
        raise EmailSendError(str(exc)) from exc
    except OSError as exc:
        raise EmailSendError(str(exc)) from exc
