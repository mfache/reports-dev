% # Layout global "Grande Poupée"
<!DOCTYPE html>
<html lang="fr" class="dark">
<head>
    <meta charset="utf-8">
    <title>{{ get('title', 'Chantiers - Delta Thermic') }}</title>
    <link rel="manifest" href="{{get('manifest_url', BASE_PATH + '/manifest.json')}}">
    <meta name="theme-color" content="#171a21">
    <link rel="apple-touch-icon" href="{{BASE_PATH}}/static/dticon.png">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="{{BASE_PATH}}/static/htmx.min.js"></script>
    <style>
        :root {
            --bg-color: #171a21; --header-bg: #111318; --card-bg: #222631;
            --text-main: #e2e8f0; --text-muted: #94a3b8;
            --accent-cyan: #38bdf8; --accent-orange: #f59e0b;
            --border-color: #334155; --hover-bg: #2d3342;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0; background-color: var(--bg-color); color: var(--text-main);
        }
        header {
            background: var(--header-bg); padding: 15px 30px; display: flex;
            justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color);
        }
        header h1 { margin: 0; font-size: 1.5em; display: flex; align-items: center; gap: 5px; }
        header a { text-decoration: none; color: inherit; }
        .logo-text-delta { color: #ef4444; font-weight: 300; letter-spacing: 1px; }
        .logo-text-thermic { color: var(--text-main); font-weight: 600; letter-spacing: 1px; }

        .user-switcher {
            background: rgba(255,255,255,0.05); padding: 5px 15px; border-radius: 20px;
            border: 1px solid var(--border-color); font-size: 0.9em; display: flex; align-items: center; gap: 10px;
        }
        .user-switcher select {
            background: transparent; color: var(--accent-cyan); border: none; outline: none; cursor: pointer; font-weight: bold;
        }
        .user-switcher select option { background: var(--bg-color); color: var(--text-main); }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }

        h2 { color: var(--accent-cyan); margin-top: 40px; font-size: 1.4em; display: flex; align-items: center; gap: 10px; }
        h2::before { content: ''; display: inline-block; width: 8px; height: 8px; background-color: var(--accent-cyan); border-radius: 50%; }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
        .card {
            background: var(--card-bg); padding: 20px; border-radius: 8px; border: 1px solid var(--border-color);
            transition: all 0.2s; text-decoration: none; color: inherit; display: block; border-left: 4px solid var(--border-color);
        }
        .card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); border-left-color: var(--accent-cyan); background: var(--hover-bg); }
        .card-recent { border-left-color: var(--accent-orange); }
        .card-recent:hover { border-left-color: var(--accent-orange); }

        .card h3 { margin: 0 0 10px 0; color: var(--text-main); font-size: 1.2em; display: flex; justify-content: space-between; align-items: center; }
        .chantier-ref { color: var(--accent-cyan); }
        .card-recent .chantier-ref { color: var(--accent-orange); }

        .card p { margin: 8px 0; color: var(--text-muted); font-size: 0.95em; }
        .card .meta { font-size: 0.85em; color: #64748b; margin-top: 15px; border-top: 1px solid var(--border-color); padding-top: 12px; display: flex; justify-content: space-between; }
        .badge-recent {
            background: rgba(245, 158, 11, 0.15); color: var(--accent-orange); font-size: 0.7em;
            padding: 3px 8px; border-radius: 12px; border: 1px solid rgba(245, 158, 11, 0.3); text-transform: uppercase; letter-spacing: 0.5px;
        }
        .btn { display: inline-block; background-color: transparent; color: var(--accent-cyan); border: 1px solid var(--accent-cyan); padding: 12px 24px; text-decoration: none; border-radius: 6px; transition: all 0.2s; font-weight: bold; cursor: pointer; }
        .btn:hover { background-color: var(--accent-cyan); color: var(--bg-color); box-shadow: 0 4px 10px rgba(56, 189, 248, 0.3); }

/* Loader HTMX */
        .htmx-indicator { opacity: 0; transition: opacity 200ms ease-in; }
        .htmx-request .htmx-indicator { opacity: 1; }
        .htmx-request.htmx-indicator { opacity: 1; }

        /* Network Triangle */
        #network-triangle {
            position: fixed;
            top: 0;
            left: 0;
            width: 0;
            height: 0;
            border-style: solid;
            border-width: 40px 40px 0 0;
            border-color: #22c55e transparent transparent transparent;
            z-index: 9999;
            transition: border-color 0.4s ease;
            cursor: help;
        }
    </style>

    <script>
    // Scripts factorisés pour les tableaux (tri et filtres génériques)
    window.sortTable = function(tableId, colIndex, type, thElement) {
        const table = document.getElementById(tableId);
        if (!table) return;
        const tbody = table.tBodies[0];
        const rows = Array.from(tbody.querySelectorAll('tr'));

        const isAsc = thElement.getAttribute('data-sort') === 'asc';
        const direction = isAsc ? -1 : 1;

        // Réinitialiser tous les en-têtes
        table.querySelectorAll('th').forEach(th => {
            th.removeAttribute('data-sort');
            const icon = th.querySelector('.sort-icon');
            if(icon) icon.innerText = '';
        });

        // Appliquer le nouvel état
        thElement.setAttribute('data-sort', isAsc ? 'desc' : 'asc');
        const icon = thElement.querySelector('.sort-icon');
        if(icon) icon.innerText = isAsc ? ' ▼' : ' ▲';

        rows.sort((a, b) => {
            let aVal = a.cells[colIndex].innerText.trim();
            let bVal = b.cells[colIndex].innerText.trim();
            if (type === 'num') {
                aVal = parseInt(aVal.replace(/[^0-9-]/g, '')) || 0;
                bVal = parseInt(bVal.replace(/[^0-9-]/g, '')) || 0;
                return (aVal - bVal) * direction;
            } else {
                return aVal.localeCompare(bVal, undefined, {numeric: true}) * direction;
            }
        });
        rows.forEach(row => tbody.appendChild(row));
    };

    window.genericTableFilter = function(tableId, searchInputId, selects) {
        const searchInput = document.getElementById(searchInputId);
        const searchRaw = searchInput ? searchInput.value.toLowerCase() : '';
        const searchTerms = searchRaw.split(' ').filter(t => t.length > 0);

        const filterVals = (selects || []).map(s => {
            const el = document.getElementById(s.inputId);
            return { val: el ? el.value.toLowerCase() : '', attr: s.attr };
        });

        const table = document.getElementById(tableId);
        if (!table) return;
        const rows = table.querySelectorAll('tbody tr');

        rows.forEach(row => {
            // Ne pas filtrer les lignes qui n'ont pas de données de filtrage
            if (!row.hasAttribute(filterVals.length > 0 ? filterVals[0].attr : 'style') && !row.hasAttribute('data-protocol') && !row.hasAttribute('data-status')) return;

            const rText = row.innerText.toLowerCase();
            const matchSearch = searchTerms.length === 0 || searchTerms.every(term => rText.includes(term));

            let matchSelects = true;
            for (const f of filterVals) {
                if (f.val !== '') {
                    const rVal = (row.getAttribute(f.attr) || '').toLowerCase();
                    if (rVal !== f.val) {
                        matchSelects = false;
                        break;
                    }
                }
            }
            row.style.display = (matchSearch && matchSelects) ? '' : 'none';
        });
    };
    </script>
</head>
<body hx-boost="true" hx-target="#main-content" hx-swap="innerHTML transition:true">
    % if BASE_PATH != '/reports':
    <div id="dev-banner" style="background:#f59e0b; color:#171a21; text-align:center; font-weight:700; padding:6px; letter-spacing:1px; display:flex; align-items:center; justify-content:center; gap:15px; flex-wrap:wrap;">
        <span>ENVIRONNEMENT DE DEV — base dt_dev, jamais la production</span>
        <button id="sync-prod-db-btn" onclick="syncProdDb()" style="background:#171a21; color:#f59e0b; border:none; padding:4px 10px; font-weight:700; border-radius:4px; cursor:pointer; font-size:0.85em; display:inline-flex; align-items:center; gap:5px; transition: opacity 0.2s;">
            🔄 Synchroniser depuis Prod
        </button>
    </div>
    <script>
    async function syncProdDb() {
        if (!confirm("⚠️ ATTENTION : Cette action va écraser TOUTES les données de la base de développement (dt_dev) par celles de la production. Êtes-vous sûr de vouloir continuer ?")) {
            return;
        }
        const btn = document.getElementById('sync-prod-db-btn');
        if (!btn) return;

        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.style.opacity = '0.6';
        btn.innerHTML = '⏳ Synchronisation...';

        try {
            const res = await fetch('{{BASE_PATH}}/dev/sync-db', {
                method: 'POST'
            });
            const data = await res.json();
            if (data.status === 'ok') {
                alert('✅ ' + data.message);
                window.location.reload();
            } else {
                alert('❌ Erreur : ' + (data.error || 'Une erreur inconnue est survenue.'));
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.innerHTML = originalText;
            }
        } catch (e) {
            alert('❌ Erreur réseau : ' + e.message);
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.innerHTML = originalText;
        }
    }
    </script>
    % end
    <div id="network-triangle" title="Connexion établie (En ligne)"></div>
    <header>
        <div style="display: flex; align-items: center; gap: 30px;">
            <h1>
                <a href="{{BASE_PATH}}/" style="display:flex; align-items:center; gap:5px; text-decoration: none;">
                    <span class="logo-text-delta">DELTA</span><span class="logo-text-thermic">THERMIC</span>
                </a>
                <span id="sse_api_activity" style="display:inline-block; width:10px; height:10px; background-color:#334155; border-radius:50%; margin-left:10px; transition:background-color 0.2s, box-shadow 0.2s;" title="Témoin d'activité de l'API"></span>
                <span class="htmx-indicator" style="font-size:0.5em; margin-left: 10px;">⏳</span>
            </h1>
            <nav style="display: flex; gap: 20px; padding-top: 4px;">
                % if not current_user.get('is_wait'):
                <a href="{{BASE_PATH}}/" style="color: var(--accent-cyan); font-weight: bold; text-decoration: none; font-size: 1.1em;">Accueil</a>
                <a href="{{BASE_PATH}}/nodes" style="color: var(--accent-cyan); font-weight: bold; text-decoration: none; font-size: 1.1em;">Nodes</a>
                % end
                
                % if current_user.get('is_admin'):
                <a href="{{BASE_PATH}}/maintenance/templates" style="color: var(--accent-cyan); font-weight: bold; text-decoration: none; font-size: 1.1em;">Templates</a>
                <a href="{{BASE_PATH}}/dev" style="color: var(--accent-cyan); font-weight: bold; text-decoration: none; font-size: 1.1em;">Dev</a>
                % end
            </nav>
        </div>
        <div class="user-switcher" hx-boost="false">
            % if real_user.get('is_admin'):
                <span style="color: var(--text-muted)">Admin - Switcher :</span>
                <select onchange="window.location.href='?uid='+this.value">
                    % for u in all_users:
                    <option value="{{u['id']}}" {{'selected' if u['id'] == current_user['id'] else ''}}>
                        {{u['nom']}} ({{'CA' if u['cas'] else ('Admin' if u['adm'] else 'Wait')}})
                    </option>
                    % end
                </select>
            % else:
                <span style="color: var(--accent-cyan); font-weight: bold;">
                    👤 {{current_user.get('nom', 'Inconnu')}}
                    % if current_user.get('is_wait'):
                        <span style="color: var(--accent-orange); font-size: 0.8em; margin-left: 5px;">(En attente)</span>
                    % end
                </span>
            % end
        </div>
    </header>

    <div id="main-content">
        {{!base}}
    </div>

    <script>
      if ('serviceWorker' in navigator) {
        window.addEventListener('load', function() {
          navigator.serviceWorker.register('{{BASE_PATH}}/sw.js', { scope: '{{BASE_PATH}}/' });
        });
      }

      // Gestion du statut réseau Online / Offline
      function updateNetworkStatus() {
          const triEl = document.getElementById('network-triangle');
          if (navigator.onLine) {
              triEl.style.borderTopColor = '#22c55e'; // Vert
              triEl.title = 'Connexion établie (En ligne)';
          } else {
              triEl.style.borderTopColor = '#ef4444'; // Rouge
              triEl.title = 'Aucune connexion internet (Hors ligne)';
          }
      }

      window.addEventListener('online', updateNetworkStatus);
      window.addEventListener('offline', updateNetworkStatus);

      // Init au chargement
      updateNetworkStatus();

      // SSE Global pour l'indicateur d'activité API
      let globalAppSSE = null;
      function initGlobalAppSSE() {
          if (globalAppSSE) return;
          globalAppSSE = new EventSource('{{BASE_PATH}}/reports_sse');

          globalAppSSE.onmessage = (event) => {
              try {
                  const payload = JSON.parse(event.data);
                  if (payload.api_activity) {
                      const dot = document.getElementById('sse_api_activity');
                      if (dot) {
                          // Animation de clignotement
                          dot.style.backgroundColor = '#22c55e'; // Vert
                          dot.style.boxShadow = '0 0 8px #22c55e';
                          setTimeout(() => {
                              dot.style.backgroundColor = '#334155'; // Retour au gris
                              dot.style.boxShadow = 'none';
                          }, 800); // 800ms pour qu'il soit bien visible
                      }
                  }
              } catch (e) {
                  // Ignorer si ce n'est pas du JSON
              }
          };
      }

      initGlobalAppSSE();
    </script>
</body>
</html>
