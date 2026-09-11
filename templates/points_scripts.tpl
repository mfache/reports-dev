<script>
function filterTable(hostnameSafe) {
    window.genericTableFilter(
        'table-' + hostnameSafe,
        'filter-search-' + hostnameSafe,
        [
            { inputId: 'filter-proto-' + hostnameSafe, attr: 'data-protocol' },
            { inputId: 'filter-dev-' + hostnameSafe, attr: 'data-device' }
        ]
    );
}

function onDeviceFilterChange(hostnameSafe) {
    const sel = document.getElementById('filter-dev-' + hostnameSafe);
    const btn = document.getElementById('btn-purge-dev-' + hostnameSafe);
    if (sel && btn) {
        if (sel.value && sel.value !== '') {
            btn.style.display = 'inline-block';
            btn.textContent = `🗑️ Purger "${sel.value}"`;
        } else {
            btn.style.display = 'none';
        }
    }
}

async function executePurge(chantierId, payload, targetLabel) {
    try {
        const res = await fetch(`{{BASE_PATH}}/chantier/${chantierId}/purge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alert(`Succès : ${data.deleted} relevé(s) supprimé(s) (${targetLabel}).`);
            window.location.reload();
        } else {
            alert(`Erreur : ${data.error || 'Une erreur est survenue lors de la purge.'}`);
        }
    } catch (e) {
        alert(`Erreur réseau : ${e.message}`);
    }
}

async function purgeAllChantierPoints(chantierId, chantierRef) {
    const confirmation = prompt(`ATTENTION : Vous êtes sur le point de supprimer TOUS les relevés enregistrés pour le chantier "${chantierRef}".\n\nCette action est irréversible.\n\nTapez "PURGER" pour confirmer :`);
    if (confirmation !== 'PURGER') {
        if (confirmation !== null) {
            alert('Purge annulée (mot de confirmation incorrect).');
        }
        return;
    }

    await executePurge(chantierId, {}, `Chantier "${chantierRef}"`);
}

async function purgeDeviceFromButton(btn) {
    const chantierId = btn.getAttribute('data-chantier-id');
    const hostname = btn.getAttribute('data-hostname');
    const protocol = btn.getAttribute('data-protocol');
    const device = btn.getAttribute('data-device');

    if (!confirm(`Voulez-vous vraiment supprimer tous les relevés pour l'équipement "${device}" (Boîtier : ${hostname}) ?\n\nCette action est irréversible.`)) {
        return;
    }

    await executePurge(chantierId, { boitier_id: hostname, protocol: protocol, device: device }, `Équipement "${device}"`);
}

async function purgeSelectedDeviceFromFilter(btn) {
    const chantierId = btn.getAttribute('data-chantier-id');
    const hostname = btn.getAttribute('data-hostname');
    const hostnameSafe = btn.getAttribute('data-hostname-safe');
    const sel = document.getElementById('filter-dev-' + hostnameSafe);
    if (!sel || !sel.value) return;
    const device = sel.value;

    const protoSel = document.getElementById('filter-proto-' + hostnameSafe);
    const protocol = protoSel ? protoSel.value : '';

    if (!confirm(`Voulez-vous vraiment supprimer tous les relevés pour l'équipement "${device}" (Boîtier : ${hostname}) ?\n\nCette action est irréversible.`)) {
        return;
    }

    const payload = { boitier_id: hostname, device: device };
    if (protocol) {
        payload.protocol = protocol;
    }
    await executePurge(chantierId, payload, `Équipement "${device}"`);
}

function getTrendHtml(curr, prev) {
    if (curr === null || curr === '' || prev === null || prev === '') return '';
    if (curr === prev) return '<span style="color: #94a3b8; font-size: 0.85em; margin-right: 5px;">=</span>';
    
    const cf = parseFloat(curr);
    const pf = parseFloat(prev);
    if (!isNaN(cf) && !isNaN(pf)) {
        if (cf > pf) return '<span style="color: #22c55e; font-size: 0.85em; margin-right: 5px;">▲</span>';
        if (cf < pf) return '<span style="color: #ef4444; font-size: 0.85em; margin-right: 5px;">▼</span>';
        return '<span style="color: #94a3b8; font-size: 0.85em; margin-right: 5px;">=</span>';
    } else {
        return '<span style="color: var(--accent-orange); font-size: 0.85em; margin-right: 5px;">🔄</span>';
    }
}

class SSEPointManager {
    constructor(basePath, chantierId) {
        this.basePath = basePath;
        this.chantierId = chantierId;
        this.uuid = localStorage.getItem('sse_uuid');
        this.points = new Set();
        this.eventSource = null;
        this.observer = null;
        this.pendingSync = false;
        this.syncTimeout = null;
    }

    start() {
        console.log("[SSE] Démarrage du gestionnaire de points...");
        this.connect();
        this.setupObserver();
        this.scanDOM(true); // Scan initial sans délai
    }

    connect() {
        const url = `${this.basePath}/chantier/${this.chantierId}/reports_sse` + (this.uuid ? `?uuid=${this.uuid}` : '');
        console.log(`[SSE] Connexion à ${url}`);
        this.eventSource = new EventSource(url);
        
        this.eventSource.onmessage = (e) => {
            let data = e.data;
            try {
                data = JSON.parse(e.data);
            } catch (err) {
                // Pas du JSON (ex: 'update' ou message vide)
            }
            this.handleUpdate(data);
        };

        this.eventSource.addEventListener('uuid', (e) => {
             console.log(`[SSE] UUID reçu: ${e.data}`);
             this.uuid = e.data;
             localStorage.setItem('sse_uuid', this.uuid);
             this.syncPoints([...this.points], []); // Premier enregistrement des points
        });

        this.eventSource.onerror = () => {
            console.error("[SSE] Erreur de connexion, reconnexion automatique...");
        };
    }

    setupObserver() {
        this.observer = new MutationObserver(() => {
            this.scheduleScan();
        });
        this.observer.observe(document.body, { 
            childList: true, 
            subtree: true 
        });
    }

    scheduleScan() {
        if (this.syncTimeout) clearTimeout(this.syncTimeout);
        this.syncTimeout = setTimeout(() => this.scanDOM(), 500);
    }

    scanDOM(forceSync = false) {
        const currentPoints = new Set();
        document.querySelectorAll('[data-b][data-protocol][data-device][data-obj]').forEach(el => {
            const key = `${el.dataset.b}|${el.dataset.protocol}|${el.dataset.device}|${el.dataset.obj}`;
            currentPoints.add(key);
        });

        const added = [...currentPoints].filter(p => !this.points.has(p));
        const removed = [...this.points].filter(p => !currentPoints.has(p));

        if (added.length > 0 || removed.length > 0 || forceSync) {
            console.log(`[SSE] DOM changé : +${added.length}, -${removed.length}`);
            this.points = currentPoints;
            this.syncPoints(added, removed);
        }
    }

    async syncPoints(added = [], removed = []) {
        if (!this.uuid) return;
        try {
            await fetch(`${this.basePath}/api/sse/sync`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    uuid: this.uuid,
                    added,
                    removed
                })
            });
        } catch (err) {
            console.error("[SSE] Échec de synchronisation des points", err);
        }
    }

    handleUpdate(data) {
        // Envoi d'un événement global pour les autres scripts (ex: rafraîchissement des graphiques)
        window.dispatchEvent(new CustomEvent('sse:message', { detail: data }));

        if (data === 'update') return;

        for (const [key, info] of Object.entries(data)) {
            const parts = key.split('|');
            if (parts.length !== 4) continue;
            const [b, p, d, o] = parts;

            const countEl = document.querySelector(`.trend-count-val[data-b="${b}"][data-p="${p}"][data-d="${d}"][data-o="${o}"]`);
            const valEl = document.querySelector(`.trend-val-val[data-b="${b}"][data-p="${p}"][data-d="${d}"][data-o="${o}"]`);
            const indEl = document.querySelector(`.trend-indicator[data-b="${b}"][data-p="${p}"][data-d="${d}"][data-o="${o}"]`);
            const dotEl = document.querySelector(`.update-indicator[data-b="${b}"][data-p="${p}"][data-d="${d}"][data-o="${o}"]`);

            if (countEl && info.c !== undefined) {
                countEl.innerText = info.c;
                countEl.style.color = 'var(--accent-cyan)';
                countEl.style.fontWeight = 'bold';
            }

            if (valEl && info.v !== undefined) {
                const oldVal = valEl.getAttribute('data-raw-val');
                const newVal = info.v;

                if (indEl) {
                    indEl.innerHTML = window.getTrendHtml(newVal, oldVal);
                }

                valEl.innerText = newVal;
                valEl.setAttribute('data-raw-val', newVal);

                if (dotEl) {
                    dotEl.style.opacity = '1';
                    setTimeout(() => { dotEl.style.opacity = '0'; }, 1500);
                }
            }
        }
    }
}

function startRealtimeCounts(chantierId) {
    const manager = new SSEPointManager('{{BASE_PATH}}', chantierId);
    manager.start();
    window.sseManager = manager; // Pour debug
}
</script>
