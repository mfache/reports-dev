% # Page Graphique Standalone "Poupée Moyenne" (sans layout)
<!DOCTYPE html>
<html lang="fr" class="dark">
<head>
    <meta charset="utf-8">
    <title>Graphique {{chantier['ref']}} - Delta Thermic</title>
    <link rel="manifest" href="{{manifest_url}}">
    <meta name="theme-color" content="#171a21">
    <link rel="apple-touch-icon" href="{{BASE_PATH}}/static/dticon.png">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        :root {
            --bg-color: #171a21; --header-bg: #111318;
            --text-main: #e2e8f0; --text-muted: #94a3b8;
            --accent-cyan: #38bdf8; --accent-orange: #f59e0b;
            --border-color: #334155;
        }
        * { box-sizing: border-box; }
        html, body {
            margin: 0; padding: 0; height: 100%;
            background-color: var(--bg-color); color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            overflow: hidden;
        }
        /* Force le mode paysage quel que soit l'orientation physique de
           l'appareil : cette page n'a qu'un seul but, afficher le graphique,
           qui se lit toujours mieux en largeur sur un smartphone. */
        @media screen and (orientation: portrait) {
            #app {
                position: fixed;
                top: 100%;
                left: 0;
                width: 100vh;
                height: 100vw;
                /*transform-origin: left top;*/
                /*transform: rotate(-90deg);*/
            }
        }
        #app {
            display: flex;
            flex-direction: column;
            width: 100%;
            height: 100%;
        }
        header {
            background: var(--header-bg);
            padding: 10px 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            flex-shrink: 0;
        }
        header a {
            color: var(--accent-cyan);
            text-decoration: none;
            font-size: 0.85em;
        }
        header h1 {
            margin: 0;
            font-size: 1em;
            font-weight: 600;
        }
        #chart-wrap {
            flex-grow: 1;
            min-height: 0;
            position: relative;
            padding: 10px;
        }
        footer {
            flex-shrink: 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            padding: 8px 16px;
            background: rgba(0,0,0,0.2);
            border-top: 1px solid var(--border-color);
            font-size: 0.8em;
        }
        #install-btn {
            display: none;
            background: transparent;
            border: 1px solid #22c55e;
            color: #22c55e;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
        }
        #refresh-dot {
            opacity: 0;
            color: #22c55e;
            transition: opacity 0.3s ease;
        }
        #error-msg {
            display: none;
            color: #ef4444;
            padding: 20px;
            text-align: center;
        }
        #ios-hint {
            display: none;
            padding: 6px 16px;
            background: rgba(245, 158, 11, 0.1);
            color: var(--accent-orange);
            font-size: 0.75em;
            text-align: center;
        }
    </style>
</head>
<body>
    <div id="app">
        <header>
            <h1>📈 {{chantier['ref']}}</h1>
            <a href="{{BASE_PATH}}/chantier/{{chantier['id']}}">Voir tous les points &rarr;</a>
        </header>
        <div id="chart-wrap">
            <canvas id="trendChart"></canvas>
            <p id="error-msg"></p>
        </div>
        <div id="ios-hint">Sur iPhone/iPad : bouton <strong>Partager</strong> puis <strong>«Sur l'écran d'accueil»</strong>.</div>
        <footer>
            <button id="install-btn" onclick="installShortcut()">➕ Installer</button>
            <div style="display: flex; align-items: center; gap: 6px; color: var(--text-muted);">
                <span id="refresh-dot">●</span>
                <span>Mise à jour automatique</span>
            </div>
        </footer>
    </div>

    <script src="{{BASE_PATH}}/static/chart.umd.js"></script>
    <script>
        const chantierId = {{chantier['id']}};
        const chartParam = {{!chart_param_json}};
        let chartInstance = null;

        function parsePoints(raw) {
            if (!raw) return [];
            return raw.split(';').map(pt => {
                const parts = pt.split(',');
                if (parts.length !== 4) return null;
                return { b: parts[0], p: parts[1], d: parts[2], o: parts[3] };
            }).filter(Boolean);
        }

        const points = parsePoints(chartParam);

        async function fetchChartData() {
            if (points.length === 0) return null;
            const res = await fetch(`{{BASE_PATH}}/chantier/${chantierId}/chart-data`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(points)
            });
            if (res.ok) return await res.json();
            return null;
        }

        async function renderChart() {
            const data = await fetchChartData();
            const errorEl = document.getElementById('error-msg');
            if (!data || !data.datasets || data.datasets.length === 0) {
                errorEl.textContent = 'Aucune donnée à afficher pour ce lien.';
                errorEl.style.display = 'block';
                return;
            }
            errorEl.style.display = 'none';

            const colors = ['#38bdf8', '#f59e0b', '#22c55e', '#ef4444', '#a855f7', '#ec4899', '#eab308'];
            data.datasets.forEach((ds, idx) => {
                ds.borderColor = colors[idx % colors.length];
                ds.backgroundColor = colors[idx % colors.length] + '40';
                ds.borderWidth = 2;
                ds.pointRadius = 0;
                ds.pointHoverRadius = 5;
                ds.fill = false;
                ds.tension = 0.1;
            });

            const ctx = document.getElementById('trendChart').getContext('2d');
            if (chartInstance) chartInstance.destroy();
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: { datasets: data.datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'nearest', axis: 'x', intersect: false },
                    plugins: {
                        legend: { labels: { color: '#e2e8f0', boxWidth: 12, font: { size: 10 } } },
                        tooltip: {
                            callbacks: {
                                title: (context) => new Date(context[0].parsed.x).toLocaleString('fr-FR')
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            ticks: {
                                color: '#94a3b8',
                                callback: (value) => new Date(value).toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'}),
                                maxRotation: 0
                            },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        },
                        y: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        }
                    }
                }
            });
        }

        async function refreshLoop() {
            const data = await fetchChartData();
            if (!data || !data.datasets || !chartInstance) return;
            const dot = document.getElementById('refresh-dot');
            dot.style.opacity = '1';
            setTimeout(() => dot.style.opacity = '0', 500);
            for (let i = 0; i < data.datasets.length; i++) {
                if (chartInstance.data.datasets[i]) {
                    chartInstance.data.datasets[i].data = data.datasets[i].data;
                }
            }
            chartInstance.update('none');
        }

        renderChart().then(() => {
            const chartSSE = new EventSource(`{{BASE_PATH}}/chantier/${chantierId}/reports_sse`);
            chartSSE.onmessage = async (event) => {
                // Gestion classique pour le graphique
                if (event.data === 'update') {
                    await refreshLoop();
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
                    // Ignorer silencieusement
                }
            };
        });

        // --- Installation du raccourci PWA pour ce lien precis ---
        let deferredInstallPrompt = null;
        window.addEventListener('beforeinstallprompt', (event) => {
            event.preventDefault();
            deferredInstallPrompt = event;
            document.getElementById('install-btn').style.display = 'inline-block';
        });
        async function installShortcut() {
            if (!deferredInstallPrompt) return;
            deferredInstallPrompt.prompt();
            await deferredInstallPrompt.userChoice;
            deferredInstallPrompt = null;
            document.getElementById('install-btn').style.display = 'none';
        }
        function isIOS() {
            return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                   (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
        }
        if (isIOS()) {
            document.getElementById('ios-hint').style.display = 'block';
        }

        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('{{BASE_PATH}}/sw.js', { scope: '{{BASE_PATH}}/' });
            });
        }
    </script>
</body>
</html>
