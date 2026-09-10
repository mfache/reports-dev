% # Page Graphique Standalone "Poupée Moyenne" (sans layout)
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Graphique {{chantier['ref']}} - Delta Thermic</title>
    <link rel="manifest" href="{{manifest_url}}">
    <meta name="theme-color" content="#0e1416">
    <link rel="apple-touch-icon" href="{{BASE_PATH}}/static/dticon.png">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        :root {
            --bg: #0e1416;
            --surface: #1b2122;
            --surface-low: #171d1e;
            --primary: #4cd7f6;
            --secondary: #4ae176;
            --tertiary: #ffb873;
            --error: #ffb4ab;
            --on-surface: #dee3e6;
            --on-surface-variant: #bcc9cd;
            --outline-variant: #3d494c;
            --font-ui: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Consolas, monospace;
        }
        * { box-sizing: border-box; }
        html, body {
            margin: 0; padding: 0; height: 100%;
            background-color: var(--bg); color: var(--on-surface);
            font-family: var(--font-ui);
            overflow: hidden;
        }
        @media screen and (orientation: portrait) {
            #app {
                position: fixed; top: 100%; left: 0; width: 100vh; height: 100vw;
            }
        }
        #app { display: flex; flex-direction: column; width: 100%; height: 100%; }
        header {
            background: var(--surface);
            padding: 12px 20px;
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--outline-variant); flex-shrink: 0;
        }
        header h1 { margin: 0; font-size: 1.1rem; font-weight: 700; color: var(--primary); font-family: var(--font-mono); }
        header a { color: var(--primary); text-decoration: none; font-size: 0.8rem; font-weight: 600; }
        #chart-wrap { flex-grow: 1; min-height: 0; position: relative; padding: 15px; background: var(--bg); }
        footer {
            flex-shrink: 0; display: flex; justify-content: space-between; align-items: center;
            padding: 10px 20px; background: var(--surface-low); border-top: 1px solid var(--outline-variant); font-size: 0.8rem;
        }
        #install-btn {
            display: none; background: var(--primary); color: #003640; border: none;
            padding: 6px 14px; border-radius: 4px; cursor: pointer; font-weight: 700;
        }
        #refresh-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--secondary); opacity: 0; transition: opacity 0.3s ease; display: inline-block; }
        #error-msg { display: none; color: var(--error); padding: 20px; text-align: center; font-weight: 700; }
        #ios-hint { display: none; padding: 8px; background: rgba(255, 184, 115, 0.1); color: var(--tertiary); font-size: 0.75rem; text-align: center; }
    </style>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=JetBrains+Mono:wght@700&display=swap" rel="stylesheet">
</head>
<body>
    <div id="app">
        <header>
            <h1>📈 {{chantier['ref']}}</h1>
            <a href="{{BASE_PATH}}/chantier/{{chantier['id']}}">Voir points &rarr;</a>
        </header>
        <div id="chart-wrap">
            <canvas id="trendChart"></canvas>
            <p id="error-msg"></p>
        </div>
        <div id="ios-hint">Sur iPhone/iPad : bouton <strong>Partager</strong> puis <strong>«Sur l'écran d'accueil»</strong>.</div>
        <footer>
            <button id="install-btn" onclick="installShortcut()">➕ INSTALLER</button>
            <div style="display: flex; align-items: center; gap: 10px; color: var(--on-surface-variant); font-weight: 600;">
                <span id="refresh-dot"></span>
                <span>DIRECT</span>
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
                return parts.length === 4 ? { b: parts[0], p: parts[1], d: parts[2], o: parts[3] } : null;
            }).filter(Boolean);
        }
        const points = parsePoints(chartParam);
        async function fetchChartData() {
            if (points.length === 0) return null;
            const res = await fetch(`{{BASE_PATH}}/chantier/${chantierId}/chart-data`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(points)
            });
            return res.ok ? await res.json() : null;
        }
        async function renderChart() {
            const data = await fetchChartData(), errorEl = document.getElementById('error-msg');
            if (!data || !data.datasets || data.datasets.length === 0) {
                errorEl.textContent = 'Aucune donnée à afficher.'; errorEl.style.display = 'block'; return;
            }
            errorEl.style.display = 'none';
            const colors = ['#4cd7f6', '#ffb873', '#4ae176', '#ffb4ab', '#a855f7', '#ec4899', '#eab308'];
            data.datasets.forEach((ds, idx) => {
                ds.borderColor = colors[idx % colors.length]; ds.backgroundColor = colors[idx % colors.length] + '20';
                ds.borderWidth = 2; ds.pointRadius = 0; ds.pointHoverRadius = 6; ds.tension = 0.1;
            });
            const ctx = document.getElementById('trendChart').getContext('2d');
            if (chartInstance) chartInstance.destroy();
            chartInstance = new Chart(ctx, {
                type: 'line', data: { datasets: data.datasets },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: 'nearest', axis: 'x', intersect: false },
                    plugins: {
                        legend: { labels: { color: '#bcc9cd', font: { family: 'Inter', size: 10 } } },
                        tooltip: { backgroundColor: 'rgba(9, 15, 17, 0.9)', titleFont: { family: 'JetBrains Mono' }, bodyFont: { family: 'JetBrains Mono' } }
                    },
                    scales: {
                        x: { type: 'linear', ticks: { color: '#869397', font: { family: 'JetBrains Mono', size: 9 }, callback: (v) => new Date(v).toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'}) }, grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { ticks: { color: '#869397', font: { family: 'JetBrains Mono', size: 9 } }, grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });
        }
        async function refreshLoop() {
            const data = await fetchChartData(); if (!data || !data.datasets || !chartInstance) return;
            const dot = document.getElementById('refresh-dot'); dot.style.opacity = '1'; setTimeout(() => dot.style.opacity = '0', 500);
            for (let i = 0; i < data.datasets.length; i++) if (chartInstance.data.datasets[i]) chartInstance.data.datasets[i].data = data.datasets[i].data;
            chartInstance.update('none');
        }
        renderChart().then(() => {
            const chartSSE = new EventSource(`{{BASE_PATH}}/chantier/${chantierId}/reports_sse`);
            chartSSE.onmessage = async (event) => {
                if (event.data === 'update') await refreshLoop();
            };
        });
        let deferredInstallPrompt = null;
        window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredInstallPrompt = e; document.getElementById('install-btn').style.display = 'inline-block'; });
        async function installShortcut() { if (!deferredInstallPrompt) return; deferredInstallPrompt.prompt(); await deferredInstallPrompt.userChoice; deferredInstallPrompt = null; document.getElementById('install-btn').style.display = 'none'; }
        if (/iPad|iPhone|iPod/.test(navigator.userAgent)) document.getElementById('ios-hint').style.display = 'block';
        if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('{{BASE_PATH}}/sw.js', { scope: '{{BASE_PATH}}/' }));
    </script>
</body>
</html>
