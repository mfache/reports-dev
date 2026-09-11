import asyncio
import json
import logging
import uuid
from typing import Dict, Set

# Note: Requires aiomqtt and aiomysql
# pip install aiomqtt aiomysql
try:
    import aiomqtt
except ImportError:
    aiomqtt = None

try:
    import aiomysql
except ImportError:
    aiomysql = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sse-worker")

class SSEWorker:
    def __init__(self):
        self.client_subscriptions: Dict[str, Set[str]] = {}  # uuid -> set of "b|p|d|o"
        self.running = True

    async def run(self):
        if not aiomqtt:
            logger.error("aiomqtt non installé. Arrêt.")
            return

        async with aiomqtt.Client("127.0.0.1") as client:
            logger.info("Connecté au broker MQTT")
            await client.subscribe("reports/sse/requests")
            
            # Tâche de fond pour l'envoi périodique des mises à jour
            asyncio.create_task(self.update_loop(client))

            async with client.messages as messages:
                async for message in messages:
                    if message.topic.value == "reports/sse/requests":
                        await self.handle_request(message.payload)

    async def handle_request(self, payload):
        try:
            data = json.loads(payload)
            client_uuid = data.get("uuid")
            added = data.get("added", [])
            removed = data.get("removed", [])

            if not client_uuid:
                return

            if client_uuid not in self.client_subscriptions:
                self.client_subscriptions[client_uuid] = set()

            for p in added:
                self.client_subscriptions[client_uuid].add(p)
            
            for p in removed:
                self.client_subscriptions[client_uuid].discard(p)

            logger.info(f"Client {client_uuid} mis à jour : {len(self.client_subscriptions[client_uuid])} points")
            
            # Nettoyage si plus de points ? (Optionnel, le client peut juste se déconnecter du SSE)
        except Exception as e:
            logger.error(f"Erreur traitement requête: {e}")

    async def update_loop(self, mqtt_client):
        """Boucle d'envoi des valeurs actuelles aux clients SSE."""
        while self.running:
            await asyncio.sleep(2) # Fréquence de rafraîchissement
            
            if not self.client_subscriptions:
                continue

            try:
                # Dans un vrai scénario, on regrouperait les requêtes par chantier/boitier
                # Pour le POC, on simule ou on fait une requête simple
                updates_by_client = await self.fetch_updates()
                
                for client_uuid, update_data in updates_by_client.items():
                    if update_data:
                        await mqtt_client.publish(
                            f"reports/sse/updates/{client_uuid}",
                            json.dumps(update_data)
                        )
            except Exception as e:
                logger.error(f"Erreur dans la boucle d'update: {e}")

    async def fetch_updates(self):
        """Récupère les dernières valeurs en base pour tous les points suivis."""
        # Note: Implémentation simplifiée. Idéalement avec aiomysql.
        # Ici on se contente de simuler le retour pour l'exemple.
        results = {}
        for client_uuid, points in self.client_subscriptions.items():
            client_update = {}
            # Logique de fetch DB ici...
            # mock: client_update[point] = { 'c': 123, 'v': '45.6' }
            results[client_uuid] = client_update
        return results

if __name__ == "__main__":
    worker = SSEWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        pass
