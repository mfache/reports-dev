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
        const res = await fetch(`/reports/chantier/${chantierId}/purge`, {
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

let knownCounts = {};

function startRealtimeCounts(chantierId) {
    // Initialise l'état connu à partir de l'affichage actuel (rendu par le serveur au chargement)
    document.querySelectorAll('.trend-count-val').forEach(el => {
        const b = el.getAttribute('data-b');
        const p = el.getAttribute('data-p');
        const d = el.getAttribute('data-d');
        const o = el.getAttribute('data-o');
        const key = `${b}|${p}|${d}|${o}`;
        knownCounts[key] = parseInt(el.innerText) || 0;
    });

    setInterval(async () => {
        try {
            const res = await fetch(`/reports/chantier/${chantierId}/counts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(knownCounts)
            });
            
            if (!res.ok) return;
            
            // Le serveur ne renvoie *que* ce qui a changé
            const diff = await res.json();
            
            // S'il n'y a aucun changement, on ne fait rien
            if (Object.keys(diff).length === 0) return;
            
            // Met à jour notre état connu avec les nouvelles valeurs
            Object.assign(knownCounts, diff);
            
            document.querySelectorAll('.trend-count-val').forEach(el => {
                const b = el.getAttribute('data-b');
                const p = el.getAttribute('data-p');
                const d = el.getAttribute('data-d');
                const o = el.getAttribute('data-o');
                const key = `${b}|${p}|${d}|${o}`;
                
                // Si cette clé est présente dans le diff, c'est qu'elle a changé
                if (diff[key] !== undefined) {
                    const newVal = diff[key].c;
                    el.innerText = newVal;

                    // Restore normal styling if it was at 0
                    if (newVal > 0 && el.style.color !== 'var(--accent-cyan)') {
                        el.style.color = 'var(--accent-cyan)';
                        el.style.fontWeight = 'bold';
                        el.style.fontSize = '1em';
                    }

                    // Update corresponding value cell and trend indicator
                    const valEl = document.querySelector(`.trend-val-val[data-b="${b}"][data-p="${p}"][data-d="${d}"][data-o="${o}"]`);
                    const indEl = document.querySelector(`.trend-indicator[data-b="${b}"][data-p="${p}"][data-d="${d}"][data-o="${o}"]`);

                    if (valEl && diff[key].v !== undefined) {
                        const oldVal = valEl.getAttribute('data-raw-val');
                        const newV = diff[key].v;

                        if (indEl) {
                            indEl.innerHTML = getTrendHtml(newV, oldVal);
                        }

                        valEl.innerText = newV;
                        valEl.setAttribute('data-raw-val', newV);
                    }
                    
                    // Flash the green dot
                    const dotEl = document.querySelector(`.update-indicator[data-b="${b}"][data-p="${p}"][data-d="${d}"][data-o="${o}"]`);
                    if (dotEl) {
                        dotEl.style.opacity = '1';
                        setTimeout(() => {
                            dotEl.style.opacity = '0';
                        }, 1500);
                    }
                }
            });
        } catch (err) {
            console.error("Erreur sync counts", err);
        }
    }, 5000);
}
</script>
