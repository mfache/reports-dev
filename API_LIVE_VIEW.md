Documentation de l'API MQTT "Live View" (rpinode)

Le service `LiveView` du boîtier permet de forcer une scrutation rapide (1 seconde par défaut) sur une liste de points spécifiques (BACnet ou Modbus) et de recevoir les valeurs en temps réel.

#### 1. Piloter le flux (Topic de commande)

Pour démarrer ou arrêter un flux live, publiez un message MQTT sur le topic suivant :
👉 **`dt/cmd/<boitier_id>/live_view`**  
*(Remplacez `<boitier_id>` par le hostname du boîtier, ex: `rpi01`)*

**A. Démarrer la scrutation (`action: "start"`)**

```json
{
  "action": "start",
  "interval": 1,
  "points": [
    {
      "protocol": "bacnet",
      "device": "192.168.1.50",
      "obj": "analog-value,1"
    },
    {
      "protocol": "modbus",
      "device": "192.168.1.60",
      "obj": 42
    },
    {
      "protocol": "modbus",
      "device": "192.168.1.70",
      "obj": "reg_custom_1",
      "address": "192.168.1.70",
      "port": 502,
      "unit": 1,
      "function": 3,
      "reg": 100,
      "type": "float32",
      "scale": 0.1,
      "base": 0,
      "transport": "tcp"
    }
  ]
}
```

**Détails sur la structure des `"points"` :**
*   **BACnet :** 
    *   `protocol`: `"bacnet"`
    *   `device`: Adresse MAC/IP de l'appareil
    *   `obj`: Identifiant de l'objet BACnet (ex: `"analog-value,1"`).
*   **Modbus (Mode 1 : via ID local) :** Si le point existe dans la BDD du boîtier, il suffit de passer l'ID du point.
    *   `protocol`: `"modbus"`
    *   `device`: Identifiant de l'appareil (utilisé uniquement pour forger la clé de retour).
    *   `obj`: L'ID local du point (entier, ex: `42`). Le boîtier cherchera ses paramètres dans sa propre base de données.
*   **Modbus (Mode 2 : requêtes brutes à la volée) :** Si `address` est défini, le boîtier by-passe sa BDD et attaque directement l'appareil.
    *   `protocol`: `"modbus"`
    *   `device` & `obj`: (Requis) Chaînes arbitraires servant à identifier le point lors de la réponse.
    *   `address`: IP ou Port série (ex: `"192.168.1.70"` ou `"/dev/ttyUSB0"`).
    *   Paramètres : `port` (défaut: 502), `unit` (défaut: 1), `function` (défaut: 3), `reg` (défaut: 0), `type` (ex: `"int16"`, `"float32"`), `scale` (défaut: 1.0), `base` (défaut: 0), `transport` (ex: `"tcp"`, `"rtu"`).

**B. Arrêter la scrutation (`action: "stop"`)**

```json
{
  "action": "stop"
}
```
*Note : Envoyer "stop" vide la liste et met en pause le thread de lecture pour économiser les ressources du boîtier.*

**C. Coupure automatique après 5 minutes (côté boîtier)**

Le boîtier (`rpi01`) impose lui-même une durée maximale de scrutation rapide
de 5 minutes, afin de ne pas le surcharger indéfiniment si un utilisateur
oublie le Live View actif. C'est un comportement voulu et normal.

Côté interface (`templates/points_scripts.tpl`), le bouton Live View de la
page `chantier/<id>` reproduit ce délai (`LIVE_VIEW_MAX_DURATION_MS`) : un
compte à rebours s'affiche à côté du bouton dès l'activation, et le switch
se repositionne automatiquement sur "éteint" à l'échéance, avec un ordre
`stop` renvoyé au serveur par sécurité (idempotent, sans bloquer l'UI ni
afficher d'erreur si le boîtier avait déjà coupé de son côté).

---

#### 2. Consommer les données (Topic de retour)

Les valeurs lues sont publiées à chaque cycle (selon l'`interval`) sur le topic global suivant :
👉 **`reports/sse/updates`**

**Format du Payload (JSON) :**

```json
{
  "rpi01|bacnet|192.168.1.50|analog-value,1": {
    "v": "21.5",
    "c": 0
  },
  "rpi01|modbus|192.168.1.60|42": {
    "v": "100.0",
    "c": 0
  }
}
```

**Construction de la clé :**
La clé du dictionnaire est toujours construite selon le format strict suivant :
`"<boitier_id>|<protocol>|<device>|<obj>"`
*   `v` : Contient la valeur sous forme de chaîne de caractères (déjà formattée et mise à l'échelle pour le Modbus).
*   `c` : Code d'erreur (0 = succès). Si la lecture échoue ou si le point est injoignable, la clé n'est tout simplement pas incluse dans le payload de ce cycle.