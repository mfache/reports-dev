% # Page chantier "Poupée Moyenne"
<style>
    /* Force l'affichage en mode paysage de la fenêtre du graphique quand elle
       est ouverte automatiquement depuis un lien/QR code partagé (voir
       #chart-modal.landscape-lock), quel que soit l'orientation physique
       de l'appareil. Astuce CSS classique : pas de permission requise,
       contrairement à l'API Screen Orientation (non supportée partout). */
    @media screen and (orientation: portrait) {
        #chart-modal.landscape-lock {
            position: fixed;
            top: 100%;
            left: 0;
            width: 100vh;
            height: 100vw;
            transform-origin: left top;
            transform: rotate(90deg);
        }
    }
</style>

<div class="container">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px; flex-wrap: wrap; gap: 10px;">
        <h2>🏢 Chantier : {{chantier['ref']}}</h2>
        <div style="display: flex; gap: 10px; align-items: center;">
            <button type="button" 
                    onclick="purgeAllChantierPoints({{chantier['id']}}, '{{chantier['ref']}}')" 
                    class="btn" 
                    style="border-color: #ef4444; color: #ef4444; padding: 8px 16px; display: flex; align-items: center; gap: 6px; font-size: 0.95em;"
                    title="Supprimer tous les relevés de ce chantier">
                🗑️ Purger tout le chantier
            </button>
            <a href="{{BASE_PATH}}/" class="btn" style="padding: 8px 16px;">&larr; Retour</a>
        </div>
    </div>

    <div class="card" style="margin-top: 20px; border-left-color: var(--accent-cyan);">
        <p><strong>📍 Adresse :</strong> {{chantier['adresse'] or 'Non renseignée'}}</p>
        <p><strong>👤 Chargé d'affaires :</strong> {{chantier['charge_affaires'] or 'Non assigné'}}</p>
        % if chantier['cell_enodeb']:
        <p><strong>📡 Antenne LTE (eNodeB) :</strong> {{chantier['cell_enodeb']}} (MCC: {{chantier['cell_mcc']}}, MNC: {{chantier['cell_mnc']}})</p>
        % end
    </div>

    <h2 style="margin-top: 40px; color: var(--accent-orange);">🎛️ Boîtiers et Points Configurés</h2>

    % if not boitiers:
        <div class="card" style="margin-top: 20px; border-left-color: var(--border-color);">
            <p style="color: var(--text-muted);">Aucun boîtier n'est actuellement assigné à ce chantier.</p>
        </div>
    % else:
        % for hostname, data in boitiers.items():
            <div class="card" style="margin-top: 20px; border-left-color: var(--accent-orange);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h3 style="margin: 0;">Boîtier : <span style="color: var(--text-main);">{{hostname}}</span></h3>
                    % if data['tailscale_name']:
                        <span class="badge-recent" style="background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); border-color: rgba(56, 189, 248, 0.3);">{{data['tailscale_name']}}</span>
                    % end
                </div>

                % if not data['points']:
                    <p style="color: var(--text-muted); font-style: italic;">Aucun point configuré pour ce boîtier.</p>
                % else:
                    % include('points_table.tpl', hostname=hostname, points=data['points'], bacnet_aliases=bacnet_aliases, chantier=chantier)
                % end
            </div>
        % end

    % if boitiers:
        % include('points_scripts.tpl', BASE_PATH=BASE_PATH)
        <script>startRealtimeCounts({{chantier['id']}});</script>

        <script src="{{BASE_PATH}}/static/chart.umd.js"></script>
        <script src="{{BASE_PATH}}/static/qrcode.min.js"></script>

        <!-- Floating Selection Buttons -->
        <div id="floating-selection-btns" style="display: none; position: fixed; bottom: 20px; left: 20px; z-index: 1000; gap: 10px;">
            <button onclick="selectAllPoints()" style="background: rgba(34, 38, 49, 0.9); color: var(--text-main); border: 1px solid var(--border-color); padding: 8px 16px; border-radius: 6px; font-size: 0.95em; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.3); backdrop-filter: blur(4px); transition: background 0.2s;" onmouseover="this.style.background='rgba(51, 65, 85, 0.9)'" onmouseout="this.style.background='rgba(34, 38, 49, 0.9)'">
                Tous
            </button>
            <button onclick="clearChartSelection()" style="background: rgba(34, 38, 49, 0.9); color: var(--text-main); border: 1px solid var(--border-color); padding: 8px 16px; border-radius: 6px; font-size: 0.95em; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.3); backdrop-filter: blur(4px); transition: background 0.2s;" onmouseover="this.style.background='rgba(51, 65, 85, 0.9)'" onmouseout="this.style.background='rgba(34, 38, 49, 0.9)'">
                Aucun
            </button>
        </div>

        <!-- Floating Chart Button -->
        <div id="floating-chart-btn" style="display: none; position: fixed; bottom: 20px; right: 20px; z-index: 1000;">
            <button onclick="openChartModal()" style="background: rgba(34, 38, 49, 0.9); color: var(--accent-cyan); border: 1px solid var(--accent-cyan); padding: 8px 16px; border-radius: 6px; font-size: 0.95em; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.3); display: flex; align-items: center; gap: 6px; backdrop-filter: blur(4px); transition: background 0.2s;">
                Voir le graphique (<span id="chart-selection-count" style="font-weight: bold;">0</span>)
            </button>
        </div>

        <!-- Chart Modal -->
        <div id="chart-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 2000; align-items: center; justify-content: center;">
            <div style="background: var(--bg-color); width: 90%; max-width: 1000px; border-radius: 12px; border: 1px solid var(--border-color); display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <div style="padding: 15px 20px; background: var(--header-bg); border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; color: var(--accent-cyan);">Graphique des points sélectionnés</h3>
                    <button onclick="closeChartModal()" style="background: transparent; border: none; color: var(--text-muted); font-size: 1.5em; cursor: pointer;">&times;</button>
                </div>
                <div style="padding: 20px; position: relative; height: 60vh; display: flex;">
                    <div style="flex-grow: 1; min-width: 0; position: relative;">
                        <canvas id="trendChart"></canvas>
                    </div>
                    <div id="qr-code-container" style="display: none; width: 220px; flex-shrink: 0; background: white; border-radius: 8px; margin-left: 20px; padding: 10px; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.2); position: relative; z-index: 5;">
                        <img id="qr-code-img" width="200" height="200" style="width: 200px; height: 200px;" alt="QR Code">
                        <p id="qr-code-error" style="display: none; color: #c62828; font-size: 0.8em; text-align: center; font-weight: bold; word-break: break-word;"></p>
                        <p style="color: black; margin-top: 10px; font-size: 0.85em; text-align: center; font-weight: bold;">Scannez pour suivre sur mobile</p>
                    </div>
                </div>
                <div id="ios-install-hint" style="display: none; padding: 8px 20px; background: rgba(245, 158, 11, 0.1); border-top: 1px solid rgba(245, 158, 11, 0.2); font-size: 0.85em; color: var(--accent-orange); text-align: center;">
                    Sur iPhone/iPad : appuyez sur le bouton <strong>Partager</strong> de Safari, puis <strong>«Sur l'écran d'accueil»</strong> pour enregistrer ce graphique.
                </div>
                <div style="padding: 15px 20px; background: rgba(0,0,0,0.2); border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                    <div style="display: flex; gap: 10px;">
                        <button onclick="toggleQRCode()" style="background: transparent; border: 1px solid var(--accent-orange); color: var(--accent-orange); padding: 8px 16px; border-radius: 6px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='rgba(245, 158, 11, 0.1)'" onmouseout="this.style.background='transparent'">📱 QR Code (Mobile)</button>
                        <button id="install-shortcut-btn" onclick="installShortcut()" style="display: none; background: transparent; border: 1px solid #22c55e; color: #22c55e; padding: 8px 16px; border-radius: 6px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='rgba(34, 197, 94, 0.1)'" onmouseout="this.style.background='transparent'">➕ Installer ce graphique</button>
                    </div>
                    <div style="display: flex; gap: 15px; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span id="chart-refresh-indicator" style="opacity: 0; color: #22c55e; transition: opacity 0.3s ease;">●</span>
                        <span style="font-size: 0.85em; color: var(--text-muted);">Mise à jour automatique en direct</span>
                    </div>
                    <button onclick="clearChartSelection()" style="background: transparent; border: 1px solid var(--text-muted); color: var(--text-muted); padding: 8px 16px; border-radius: 6px; cursor: pointer;">Vider la sélection</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
        let chartInstance = null;

        let selectedPoints = []; // Array of {b, p, d, o}

        function toggleRowSelection(row) {
            const b = row.getAttribute('data-b');
            const p = row.getAttribute('data-protocol');
            const d = row.getAttribute('data-device');
            const o = row.getAttribute('data-obj');
            const labelCell = row.querySelector('.point-label');

            const index = selectedPoints.findIndex(pt => pt.b === b && pt.p === p && pt.d === d && pt.o === o);

            if (index > -1) {
                // Remove it
                selectedPoints.splice(index, 1);
                labelCell.style.fontWeight = 'normal';
                labelCell.style.color = 'inherit';
            } else {
                // Add it
                selectedPoints.push({b, p, d, o});
                labelCell.style.fontWeight = 'bold';
                labelCell.style.color = 'var(--accent-cyan)';
            }

            updateChartButton();
        }

        function updateChartButton() {
            const btnRight = document.getElementById('floating-chart-btn');
            const btnLeft = document.getElementById('floating-selection-btns');
            const countSpan = document.getElementById('chart-selection-count');

            if (selectedPoints.length > 0) {
                countSpan.innerText = selectedPoints.length;
                btnRight.style.display = 'block';
                btnLeft.style.display = 'flex';
            } else {
                btnRight.style.display = 'none';
                btnLeft.style.display = 'none';
            }
        }

        function selectAllPoints() {
            selectedPoints = [];
            document.querySelectorAll('tr[data-b]').forEach(row => {
                // On sélectionne uniquement les lignes qui sont actuellement visibles
                if (row.style.display !== 'none') {
                    const b = row.getAttribute('data-b');
                    const p = row.getAttribute('data-protocol');
                    const d = row.getAttribute('data-device');
                    const o = row.getAttribute('data-obj');
                    selectedPoints.push({b, p, d, o});

                    const labelCell = row.querySelector('.point-label');
                    if (labelCell) {
                        labelCell.style.fontWeight = 'bold';
                        labelCell.style.color = 'var(--accent-cyan)';
                    }
                } else {
                    const labelCell = row.querySelector('.point-label');
                    if (labelCell) {
                        labelCell.style.fontWeight = 'normal';
                        labelCell.style.color = 'inherit';
                    }
                }
            });
            updateChartButton();
        }

        function clearChartSelection() {
            selectedPoints = [];
            // Reset visually all labels
            document.querySelectorAll('.point-label').forEach(td => {
                td.style.fontWeight = 'normal';
                td.style.color = 'inherit';
            });
            updateChartButton();
            closeChartModal();
        }

        async function fetchChartData() {
            if (selectedPoints.length === 0) return null;
            const points = selectedPoints;

            if (points.length === 0) return null;

            const res = await fetch(`{{BASE_PATH}}/chantier/{{chantier['id']}}/chart-data`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(points)
            });

            if (res.ok) {
                return await res.json();
            }
            return null;
        }

        async function renderChart() {
            const data = await fetchChartData();
            if (!data || !data.datasets || data.datasets.length === 0) return;

            const ctx = document.getElementById('trendChart').getContext('2d');

            // Generate some colors
            const colors = ['#38bdf8', '#f59e0b', '#22c55e', '#ef4444', '#a855f7', '#ec4899', '#eab308'];

            data.datasets.forEach((ds, idx) => {
                ds.borderColor = colors[idx % colors.length];
                ds.backgroundColor = colors[idx % colors.length] + '40'; // with opacity
                ds.borderWidth = 2;
                ds.pointRadius = 0; // Hide points for cleaner line, show on hover
                ds.pointHoverRadius = 5;
                ds.fill = false;
                ds.tension = 0.1; // Slight curve
                ds.stepped = false; // Use stepped lines which is usually better for technical states
            });

            if (chartInstance) {
                chartInstance.destroy();
            }

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: data.datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'nearest',
                        axis: 'x',
                        intersect: false
                    },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                title: function(context) {
                                    // Format timestamp
                                    const d = new Date(context[0].parsed.x);
                                    return d.toLocaleString('fr-FR');
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'linear', // Use linear scale for timestamps
                            title: {
                                display: false
                            },
                            ticks: {
                                callback: function(value) {
                                    const d = new Date(value);
                                    return d.toLocaleTimeString('fr-FR', {hour: '2-digit', minute:'2-digit'});
                                },
                                maxRotation: 0
                            }
                        },
                        y: {
                            title: {
                                display: false
                            }
                        }
                    }
                }
            });
        }

        let globalSSE = null;

        function initGlobalSSE() {
            if (globalSSE) return;
            globalSSE = new EventSource(`{{BASE_PATH}}/chantier/{{chantier['id']}}/reports_sse`);
            
            globalSSE.onmessage = async (event) => {
                // Gestion classique (rafraîchissement graphique)
                if (event.data === 'update') {
                    const modal = document.getElementById('chart-modal');
                    if (modal && modal.style.display !== 'none' && chartInstance) {
                        const data = await fetchChartData();
                        if (!data || !data.datasets) return;

                        const ind = document.getElementById('chart-refresh-indicator');
                        if (ind) {
                            ind.style.opacity = '1';
                            setTimeout(() => ind.style.opacity = '0', 500);
                        }

                        for (let i = 0; i < data.datasets.length; i++) {
                            if (chartInstance.data.datasets[i]) {
                                chartInstance.data.datasets[i].data = data.datasets[i].data;
                            }
                        }
                        chartInstance.update('none');
                    }
                    return;
                }

                // Gestion générique pour l'injection JSON dans les éléments sse_*
                try {
                    const payload = JSON.parse(event.data);
                    for (const [key, value] of Object.entries(payload)) {
                        if (key.startsWith('sse_')) {
                            // 1. Mise à jour par ID (<div id="sse_xxx">)
                            const elById = document.getElementById(key);
                            if (elById) {
                                elById.innerHTML = value;
                            }

                            // 2. Mise à jour par classe CSS (<div class="sse_xxx">)
                            const elsByClass = document.querySelectorAll(`.${key}`);
                            elsByClass.forEach(el => {
                                el.innerHTML = value;
                            });
                        }
                    }
                } catch (e) {
                    // Si ce n'est pas du JSON, on ignore silencieusement
                }
            };
        }

        async function openChartModal() {
            document.getElementById('chart-modal').style.display = 'flex';
            await renderChart();
            
            // On s'assure que le SSE global est bien démarré
            initGlobalSSE();
        }

        function closeChartModal() {
            document.getElementById('chart-modal').style.display = 'none';
            // On ne ferme plus le SSE, il reste ouvert pour mettre à jour
            // les autres éléments génériques (classes/id commençant par sse_)
        }

        function buildQRCodeDataUrl(text) {
            // Le canevas de travail n'est JAMAIS inséré dans le DOM : un canevas
            // "hors écran" se dessine toujours correctement, quel que soit l'état
            // de visibilité du reste de la page (contrairement à un canevas placé
            // dans un conteneur "display: none", qui peut ne pas se repeindre tant
            // qu'un nouveau calcul de mise en page n'a pas lieu).
            const qr = qrcode(0, 'M'); // 0 = taille automatique, M = correction d'erreur moyenne
            qr.addData(text);
            qr.make();

            const moduleCount = qr.getModuleCount();
            const cellSize = 8;
            const margin = cellSize * 2;
            const size = moduleCount * cellSize + margin * 2;

            const canvas = document.createElement('canvas');
            canvas.width = size;
            canvas.height = size;
            const ctx = canvas.getContext('2d');

            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, size, size);

            for (let row = 0; row < moduleCount; row++) {
                for (let col = 0; col < moduleCount; col++) {
                    if (qr.isDark(row, col)) {
                        ctx.fillStyle = 'black';
                        ctx.fillRect(margin + col * cellSize, margin + row * cellSize, cellSize, cellSize);
                    }
                }
            }

            return canvas.toDataURL('image/png');
        }

        function toggleQRCode() {
            const qrContainer = document.getElementById('qr-code-container');
            const isCurrentlyOpen = qrContainer.style.display === 'flex';

            if (isCurrentlyOpen) {
                qrContainer.style.display = 'none';
                // Le graphique reprend toute la largeur : on force Chart.js a
                // recalculer la taille de son canevas immediatement (sans
                // attendre son detecteur de redimensionnement automatique).
                if (chartInstance) chartInstance.resize();
                return;
            }

            // On affiche TOUJOURS le panneau en l'ouvrant, quoi qu'il arrive :
            // meme si la generation du QR echoue, l'utilisateur doit voir le
            // panneau (avec un message d'erreur clair) plutot que de croire
            // que le bouton ne fait rien.
            qrContainer.style.display = 'flex';
            if (chartInstance) chartInstance.resize();

            const img = document.getElementById('qr-code-img');
            const errorEl = document.getElementById('qr-code-error');
            errorEl.style.display = 'none';
            errorEl.textContent = '';
            img.style.display = 'block';

            if (!selectedPoints || selectedPoints.length === 0) {
                img.style.display = 'none';
                errorEl.textContent = 'Aucun point selectionne.';
                errorEl.style.display = 'block';
                return;
            }

            try {
                const chartParam = selectedPoints.map(pt => `${pt.b},${pt.p},${pt.d},${pt.o}`).join(';');
                // Le QR pointe vers une page dediee, minimale (juste le graphique,
                // sans le tableau ni la navigation), plus adaptee a un usage mobile
                // rapide sur le terrain.
                const url = window.location.origin + `{{BASE_PATH}}/chantier/{{chantier['id']}}/graph` + '?chart=' + encodeURIComponent(chartParam);

                const dataUrl = buildQRCodeDataUrl(url);
                img.src = dataUrl;
            } catch (err) {
                console.error('Erreur génération QR code :', err);
                img.style.display = 'none';
                errorEl.textContent = 'Erreur de generation : ' + err.message;
                errorEl.style.display = 'block';
            }
        }

        // --- Installation du raccourci (PWA) pour ce graphique precis ---
        let deferredInstallPrompt = null;

        window.addEventListener('beforeinstallprompt', (event) => {
            // Chrome/Edge (Android, desktop) : on intercepte l'invite native
            // pour proposer notre propre bouton, plus visible et explicite.
            event.preventDefault();
            deferredInstallPrompt = event;
            const btn = document.getElementById('install-shortcut-btn');
            if (btn) btn.style.display = 'inline-block';
        });

        async function installShortcut() {
            if (!deferredInstallPrompt) return;
            deferredInstallPrompt.prompt();
            await deferredInstallPrompt.userChoice;
            deferredInstallPrompt = null;
            document.getElementById('install-shortcut-btn').style.display = 'none';
        }

        function isIOS() {
            return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                   (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
        }

        window.addEventListener('DOMContentLoaded', () => {
            const params = new URLSearchParams(window.location.search);
            const chartData = params.get('chart');
            if (chartData) {
                selectedPoints = [];
                const pts = chartData.split(';');
                pts.forEach(pt => {
                    const parts = pt.split(',');
                    if (parts.length === 4) {
                        const b = parts[0], p = parts[1], d = parts[2], o = parts[3];
                        selectedPoints.push({b, p, d, o});

                        // Try to highlight if visible on page
                        const row = document.querySelector(`tr[data-b="${b}"][data-protocol="${p}"][data-device="${d}"][data-obj="${o}"]`);
                        if (row) {
                            const labelCell = row.querySelector('.point-label');
                            if (labelCell) {
                                labelCell.style.fontWeight = 'bold';
                                labelCell.style.color = 'var(--accent-cyan)';
                            }
                        }
                    }
                });
                if (selectedPoints.length > 0) {
                    updateChartButton();
                    // Ouverture automatique (typiquement suite à un scan de QR code) :
                    // on force l'affichage en paysage, plus adapté à la lecture d'un
                    // graphique sur smartphone, et on affiche l'astuce d'installation
                    // manuelle sur iOS (qui ne déclenche jamais 'beforeinstallprompt').
                    document.getElementById('chart-modal').classList.add('landscape-lock');
                    if (isIOS()) {
                        document.getElementById('ios-install-hint').style.display = 'block';
                    }
                    openChartModal();
                }
            }
        });
        
        // Démarrage du flux SSE global pour toute la page (graphique + injections génériques sse_*)
        initGlobalSSE();

</script>
    % end
</div>
