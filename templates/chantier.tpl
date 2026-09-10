% # Page chantier "Poupée Moyenne" (Kinetic Infrastructure)
<style>
    /* Force landscape on mobile for chart modal */
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
    .point-label.selected {
        color: var(--primary);
        font-weight: 700;
    }
    tr.selected {
        background: rgba(76, 215, 246, 0.08) !important;
    }
</style>

<div class="header-with-actions">
    <div style="display: flex; align-items: center; gap: 15px;">
        <a href="{{BASE_PATH}}/" class="btn-secondary btn-sm" hx-boost="true">
            <span class="material-symbols-outlined">arrow_back</span>
        </a>
        <div>
            <h2 style="margin: 0;">🏢 Chantier : <span class="text-primary">{{chantier['ref']}}</span></h2>
            <p class="hint" style="margin: 0;">{{chantier['adresse'] or 'Adresse non renseignée'}}</p>
        </div>
    </div>
    <div style="display: flex; gap: 10px;">
        <button type="button" 
                onclick="purgeAllChantierPoints({{chantier['id']}}, '{{chantier['ref']}}')" 
                class="btn-danger btn-sm">
            <span class="material-symbols-outlined">delete_sweep</span> Purger Relevés
        </button>
    </div>
</div>

<div class="stats-banner" style="justify-content: flex-start; gap: 40px;">
    <div class="stat-item" style="text-align: left;">
        <div class="stat-lbl">Chargé d'affaires</div>
        <div class="stat-val" style="font-size: 1.1rem; color: var(--on-surface);">{{chantier['charge_affaires'] or 'Non assigné'}}</div>
    </div>
    % if chantier['cell_enodeb']:
    <div class="stat-divider"></div>
    <div class="stat-item" style="text-align: left;">
        <div class="stat-lbl">Antenne LTE (eNodeB)</div>
        <div class="stat-val font-mono" style="font-size: 1rem; color: var(--tertiary);">{{chantier['cell_enodeb']}} <small style="font-size: 0.7rem; color: var(--outline);">({{chantier['cell_mcc']}}-{{chantier['cell_mnc']}})</small></div>
    </div>
    % end
</div>

% if not boitiers:
    <div class="card luminescent-border">
        <div style="display: flex; align-items: center; gap: 15px; color: var(--outline);">
            <span class="material-symbols-outlined" style="font-size: 32px;">info</span>
            <p style="margin: 0;">Aucun boîtier n'est actuellement assigné à ce chantier.</p>
        </div>
    </div>
% else:
    % for hostname, data in boitiers.items():
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--outline-variant); padding-bottom: 12px;">
                <h3 style="margin: 0; display: flex; align-items: center; gap: 10px;">
                    <span class="material-symbols-outlined text-primary">developer_board</span>
                    Boîtier : <span class="text-primary font-mono">{{hostname}}</span>
                </h3>
                % if data['tailscale_name']:
                    <div class="user-badge" style="background: rgba(74, 225, 118, 0.05); border-color: var(--secondary);">
                        <span class="material-symbols-outlined icon-sm text-secondary">vpn_lock</span>
                        <span class="text-secondary" style="font-size: 0.75rem; font-weight: 700; font-family: var(--font-mono);">{{data['tailscale_name']}}</span>
                    </div>
                % end
            </div>

            % if not data['points']:
                <p class="hint">Aucun point configuré pour ce boîtier.</p>
            % else:
                % include('points_table.tpl', hostname=hostname, points=data['points'], bacnet_aliases=bacnet_aliases, chantier=chantier)
            % end
        </div>
    % end

    % include('points_scripts.tpl', BASE_PATH=BASE_PATH)
    <script>startRealtimeCounts({{chantier['id']}});</script>

    <script src="{{BASE_PATH}}/static/chart.umd.js"></script>
    <script src="{{BASE_PATH}}/static/qrcode.min.js"></script>

    <!-- Floating UI Controls -->
    <div id="floating-selection-btns" style="display: none; position: fixed; bottom: 30px; left: 300px; z-index: 1000; gap: 10px;">
        <button onclick="selectAllPoints()" class="btn-secondary" style="background: rgba(23, 29, 30, 0.9); border-radius: 999px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);">
            <span class="material-symbols-outlined">checklist</span> Tous
        </button>
        <button onclick="clearChartSelection()" class="btn-secondary" style="background: rgba(23, 29, 30, 0.9); border-radius: 999px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);">
            <span class="material-symbols-outlined">close</span> Aucun
        </button>
    </div>

    <div id="floating-chart-btn" style="display: none; position: fixed; bottom: 30px; right: 40px; z-index: 1000;">
        <button onclick="openChartModal()" class="btn-primary" style="padding: 14px 28px; border-radius: 999px; box-shadow: 0 10px 40px rgba(76, 215, 246, 0.4);">
            <span class="material-symbols-outlined" style="font-size: 24px;">show_chart</span>
            Voir le graphique (<span id="chart-selection-count">0</span>)
        </button>
    </div>

    <!-- Chart Modal (Russian Doll Fragment) -->
    <div id="chart-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(9, 15, 17, 0.95); z-index: 2000; align-items: center; justify-content: center; backdrop-filter: blur(8px);">
        <div class="card luminescent-border" style="width: 94%; max-width: 1100px; padding: 0; overflow: hidden; background: var(--surface);">
            <div style="padding: 16px 24px; background: var(--surface-low); border-bottom: 1px solid var(--outline-variant); display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; display: flex; align-items: center; gap: 10px;">
                    <span class="material-symbols-outlined text-primary">analytics</span>
                    Analyse des tendances
                </h3>
                <button onclick="closeChartModal()" class="btn-close">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            
            <div style="padding: 24px; position: relative;">
                <div style="height: 55vh; min-height: 300px; display: flex; gap: 24px;">
                    <div style="flex-grow: 1; min-width: 0; position: relative; background: var(--surface-lowest); border-radius: var(--radius); border: 1px solid var(--outline-variant); padding: 10px;">
                        <canvas id="trendChart"></canvas>
                    </div>
                    
                    <div id="qr-code-container" style="display: none; width: 240px; flex-shrink: 0; background: white; border-radius: var(--radius-lg); padding: 20px; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
                        <img id="qr-code-img" width="200" height="200" style="width: 180px; height: 200px; margin-bottom: 15px;" alt="QR Code">
                        <p id="qr-code-error" style="display: none; color: #c62828; font-size: 0.8rem; font-weight: 700;"></p>
                        <p style="color: #0e1416; font-size: 0.85rem; font-weight: 700; margin: 0;">📱 SCANNEZ POUR MOBILE</p>
                        <p style="color: #666; font-size: 0.7rem; margin-top: 5px;">Suivi temps réel sur le terrain</p>
                    </div>
                </div>

                <div id="ios-install-hint" style="display: none; margin-top: 15px; padding: 10px; background: rgba(255, 184, 115, 0.1); border: 1px solid rgba(255, 184, 115, 0.2); border-radius: var(--radius); font-size: 0.8rem; color: var(--tertiary); text-align: center;">
                    💡 <strong>iPhone/iPad :</strong> appuyez sur <span class="material-symbols-outlined icon-sm">ios_share</span> puis <strong>«Sur l'écran d'accueil»</strong>.
                </div>
            </div>

            <div style="padding: 16px 24px; background: var(--surface-low); border-top: 1px solid var(--outline-variant); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <div style="display: flex; gap: 12px;">
                    <button onclick="toggleQRCode()" class="btn-orange btn-sm">
                        <span class="material-symbols-outlined icon-sm">qr_code_2</span> QR Code
                    </button>
                    <button id="install-shortcut-btn" onclick="installShortcut()" class="btn-primary btn-sm" style="display: none; box-shadow: none;">
                        <span class="material-symbols-outlined icon-sm">add_to_home_screen</span> Installer PWA
                    </button>
                </div>
                <div style="display: flex; gap: 20px; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span id="chart-refresh-indicator" class="pulse-dot" style="opacity: 0; background-color: var(--secondary);"></span>
                        <span style="font-size: 0.8rem; color: var(--on-surface-variant); font-weight: 600;">Flux temps réel actif</span>
                    </div>
                    <button onclick="clearChartSelection()" class="btn-secondary btn-sm">Vider la sélection</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let chartInstance = null;
        let selectedPoints = [];

        function toggleRowSelection(row) {
            const b = row.getAttribute('data-b');
            const p = row.getAttribute('data-protocol');
            const d = row.getAttribute('data-device');
            const o = row.getAttribute('data-obj');
            const labelCell = row.querySelector('.point-label');

            const index = selectedPoints.findIndex(pt => pt.b === b && pt.p === p && pt.d === d && pt.o === o);

            if (index > -1) {
                selectedPoints.splice(index, 1);
                labelCell.classList.remove('selected');
                row.classList.remove('selected');
            } else {
                selectedPoints.push({b, p, d, o});
                labelCell.classList.add('selected');
                row.classList.add('selected');
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
                if (row.style.display !== 'none') {
                    const b = row.getAttribute('data-b'), p = row.getAttribute('data-protocol'), d = row.getAttribute('data-device'), o = row.getAttribute('data-obj');
                    selectedPoints.push({b, p, d, o});
                    row.querySelector('.point-label').classList.add('selected');
                    row.classList.add('selected');
                }
            });
            updateChartButton();
        }

        function clearChartSelection() {
            selectedPoints = [];
            document.querySelectorAll('tr[data-b]').forEach(row => {
                row.querySelector('.point-label').classList.remove('selected');
                row.classList.remove('selected');
            });
            updateChartButton();
            closeChartModal();
        }

        async function fetchChartData() {
            if (selectedPoints.length === 0) return null;
            const res = await fetch(`{{BASE_PATH}}/chantier/{{chantier['id']}}/chart-data`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(selectedPoints)
            });
            return res.ok ? await res.json() : null;
        }

        async function renderChart() {
            const data = await fetchChartData();
            if (!data || !data.datasets || data.datasets.length === 0) return;

            const ctx = document.getElementById('trendChart').getContext('2d');
            const colors = ['#4cd7f6', '#ffb873', '#4ae176', '#ffb4ab', '#a855f7', '#ec4899', '#eab308'];

            data.datasets.forEach((ds, idx) => {
                ds.borderColor = colors[idx % colors.length];
                ds.backgroundColor = colors[idx % colors.length] + '20';
                ds.borderWidth = 2;
                ds.pointRadius = 0;
                ds.pointHoverRadius = 6;
                ds.tension = 0.1;
            });

            if (chartInstance) chartInstance.destroy();
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: { datasets: data.datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'nearest', axis: 'x', intersect: false },
                    plugins: {
                        legend: { labels: { color: '#bcc9cd', font: { family: 'Inter', size: 11 } } },
                        tooltip: {
                            backgroundColor: 'rgba(9, 15, 17, 0.9)',
                            titleFont: { family: 'JetBrains Mono' },
                            bodyFont: { family: 'JetBrains Mono' },
                            callbacks: { title: (c) => new Date(c[0].parsed.x).toLocaleString('fr-FR') }
                        }
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            ticks: { 
                                color: '#869397',
                                callback: (v) => new Date(v).toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'}),
                                font: { family: 'JetBrains Mono', size: 10 }
                            },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        },
                        y: { 
                            ticks: { color: '#869397', font: { family: 'JetBrains Mono', size: 10 } },
                            grid: { color: 'rgba(255,255,255,0.05)' }
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
                if (event.data === 'update') {
                    const modal = document.getElementById('chart-modal');
                    if (modal && modal.style.display !== 'none' && chartInstance) {
                        const data = await fetchChartData();
                        if (!data || !data.datasets) return;
                        const ind = document.getElementById('chart-refresh-indicator');
                        if (ind) { ind.style.opacity = '1'; setTimeout(() => ind.style.opacity = '0', 500); }
                        for (let i = 0; i < data.datasets.length; i++) {
                            if (chartInstance.data.datasets[i]) chartInstance.data.datasets[i].data = data.datasets[i].data;
                        }
                        chartInstance.update('none');
                    }
                    return;
                }
                try {
                    const payload = JSON.parse(event.data);
                    for (const [key, value] of Object.entries(payload)) {
                        if (key.startsWith('sse_')) {
                            const elById = document.getElementById(key);
                            if (elById) elById.innerHTML = value;
                            document.querySelectorAll(`.${key}`).forEach(el => el.innerHTML = value);
                        }
                    }
                } catch (e) {}
            };
        }

        async function openChartModal() {
            document.getElementById('chart-modal').style.display = 'flex';
            await renderChart();
            initGlobalSSE();
        }

        function closeChartModal() {
            document.getElementById('chart-modal').style.display = 'none';
        }

        function buildQRCodeDataUrl(text) {
            const qr = qrcode(0, 'M');
            qr.addData(text);
            qr.make();
            const moduleCount = qr.getModuleCount(), cellSize = 8, margin = cellSize * 2, size = moduleCount * cellSize + margin * 2;
            const canvas = document.createElement('canvas');
            canvas.width = size; canvas.height = size;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'white'; ctx.fillRect(0, 0, size, size);
            for (let row = 0; row < moduleCount; row++) {
                for (let col = 0; col < moduleCount; col++) {
                    if (qr.isDark(row, col)) { ctx.fillStyle = 'black'; ctx.fillRect(margin + col * cellSize, margin + row * cellSize, cellSize, cellSize); }
                }
            }
            return canvas.toDataURL('image/png');
        }

        function toggleQRCode() {
            const qrContainer = document.getElementById('qr-code-container');
            const isCurrentlyOpen = qrContainer.style.display === 'flex';
            if (isCurrentlyOpen) {
                qrContainer.style.display = 'none';
                if (chartInstance) chartInstance.resize();
                return;
            }
            qrContainer.style.display = 'flex';
            if (chartInstance) chartInstance.resize();
            const img = document.getElementById('qr-code-img'), errorEl = document.getElementById('qr-code-error');
            errorEl.style.display = 'none'; img.style.display = 'block';
            if (!selectedPoints || selectedPoints.length === 0) {
                img.style.display = 'none'; errorEl.textContent = 'Aucun point sélectionné.'; errorEl.style.display = 'block'; return;
            }
            try {
                const chartParam = selectedPoints.map(pt => `${pt.b},${pt.p},${pt.d},${pt.o}`).join(';');
                const url = window.location.origin + `{{BASE_PATH}}/chantier/{{chantier['id']}}/graph` + '?chart=' + encodeURIComponent(chartParam);
                img.src = buildQRCodeDataUrl(url);
            } catch (err) {
                img.style.display = 'none'; errorEl.textContent = 'Erreur : ' + err.message; errorEl.style.display = 'block';
            }
        }

        let deferredInstallPrompt = null;
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault(); deferredInstallPrompt = e;
            const btn = document.getElementById('install-shortcut-btn');
            if (btn) btn.style.display = 'inline-flex';
        });

        async function installShortcut() {
            if (!deferredInstallPrompt) return;
            deferredInstallPrompt.prompt();
            await deferredInstallPrompt.userChoice;
            deferredInstallPrompt = null;
            document.getElementById('install-shortcut-btn').style.display = 'none';
        }

        window.addEventListener('DOMContentLoaded', () => {
            const params = new URLSearchParams(window.location.search);
            const chartData = params.get('chart');
            if (chartData) {
                selectedPoints = [];
                chartData.split(';').forEach(pt => {
                    const parts = pt.split(',');
                    if (parts.length === 4) {
                        const b = parts[0], p = parts[1], d = parts[2], o = parts[3];
                        selectedPoints.push({b, p, d, o});
                        const row = document.querySelector(`tr[data-b="${b}"][data-protocol="${p}"][data-device="${d}"][data-obj="${o}"]`);
                        if (row) { row.querySelector('.point-label').classList.add('selected'); row.classList.add('selected'); }
                    }
                });
                if (selectedPoints.length > 0) {
                    updateChartButton();
                    document.getElementById('chart-modal').classList.add('landscape-lock');
                    if (/iPad|iPhone|iPod/.test(navigator.userAgent)) document.getElementById('ios-install-hint').style.display = 'block';
                    openChartModal();
                }
            }
        });
        initGlobalSSE();
    </script>
% end
