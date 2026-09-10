% # Layout global "Grande Poupée" (Kinetic Infrastructure Design)
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#0e1416">
    <title>{{ get('title', 'Chantiers - Deltathermic') }}</title>
    
    <link rel="manifest" href="{{get('manifest_url', BASE_PATH + '/manifest.json')}}">
    <link rel="apple-touch-icon" href="{{BASE_PATH}}/static/dticon.png">
    
    <!-- Design System Fonts & Icons -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
    
    <!-- Base Style (Kinetic Infrastructure) -->
    <link rel="stylesheet" href="{{BASE_PATH}}/static/style.css">
    
    <script src="{{BASE_PATH}}/static/htmx.min.js"></script>
</head>
<body hx-boost="true" hx-target="#main-content" hx-swap="innerHTML transition:true">
    % if BASE_PATH != '/reports':
    <div id="dev-banner" style="background:#f59e0b; color:#0e1416; text-align:center; font-weight:700; padding:6px; letter-spacing:1px; display:flex; align-items:center; justify-content:center; gap:15px; flex-wrap:wrap; z-index: 2000; position: relative;">
        <span class="material-symbols-outlined">construction</span>
        <span>ENVIRONNEMENT DE DEV — base dt_dev, jamais la production</span>
        <button id="sync-prod-db-btn" onclick="syncProdDb()" class="btn-primary-sm" style="background:#0e1416; color:#f59e0b; border:none; box-shadow: none;">
            <span class="material-symbols-outlined icon-sm">sync</span> Synchroniser depuis Prod
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
        btn.innerHTML = '<span class="material-symbols-outlined icon-sm">hourglass_empty</span> Synchronisation...';

        try {
            const res = await fetch('{{BASE_PATH}}/dev/sync-db', { method: 'POST' });
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

    <header class="app-header">
        <div class="header-content">
            <div class="header-left">
                <a href="{{BASE_PATH}}/" class="brand-link">
                    <img src="{{BASE_PATH}}/static/DELTA-Thermic-v3_reverse.png" alt="Deltathermic" class="brand-logo">
                </a>
                
                <div class="header-divider"></div>
                
                <div class="host-info">
                    <div class="host-title-row">
                        <h2 class="host-name">REPORTS SERVER</h2>
                        <span id="sse_api_activity" title="Activité API" class="pulse-dot" style="background-color: var(--outline-variant); box-shadow: none;"></span>
                        <span class="htmx-indicator" style="font-size:0.8rem; margin-left: 5px; color: var(--primary);">⏳</span>
                    </div>
                    <div class="host-telemetry">
                        <span class="telemetry-item">FLOTTE RÉSEAU</span>
                        <span class="telemetry-sep">•</span>
                        <span class="telemetry-item">v1.2.1</span>
                    </div>
                </div>
            </div>

            <div class="header-right">
                <div class="user-switcher" hx-boost="false">
                    % if real_user.get('is_admin'):
                        <div class="user-badge" style="background: rgba(76, 215, 246, 0.1); border-color: var(--primary);">
                            <span class="material-symbols-outlined icon-sm text-primary">admin_panel_settings</span>
                            <select onchange="window.location.href='?uid='+this.value" style="background: transparent; border: none; color: var(--primary); font-weight: 600; padding: 0; width: auto; cursor: pointer;">
                                % for u in all_users:
                                <option value="{{u['id']}}" {{'selected' if u['id'] == current_user['id'] else ''}}>
                                    {{u['nom']}} ({{'CA' if u['cas'] else ('Admin' if u['adm'] else 'Wait')}})
                                </option>
                                % end
                            </select>
                        </div>
                    % else:
                        <div class="user-badge">
                            <span class="material-symbols-outlined icon-sm">account_circle</span>
                            <span class="user-name">
                                {{current_user.get('nom', 'Inconnu')}}
                                % if current_user.get('is_wait'):
                                    <small class="text-tertiary">(En attente)</small>
                                % end
                            </span>
                        </div>
                    % end
                </div>
                
                <div class="header-actions">
                    <a href="/oauth2-google/sign_out?rd={{BASE_PATH}}/" class="btn-icon btn-icon-danger" title="Déconnexion" hx-boost="false">
                        <span class="material-symbols-outlined">power_settings_new</span>
                    </a>
                </div>
            </div>
        </div>
    </header>

    <div class="app-container">
        <nav class="sidebar">
            <ul class="nav-list">
                % if not current_user.get('is_wait'):
                <li>
                    <a href="{{BASE_PATH}}/" class="nav-item {{'active' if request_path == BASE_PATH + '/' else ''}}">
                        <span class="material-symbols-outlined">dashboard</span>
                        <span>Accueil</span>
                    </a>
                </li>
                <li>
                    <a href="{{BASE_PATH}}/nodes" class="nav-item {{'active' if '/nodes' in request_path else ''}}">
                        <span class="material-symbols-outlined">router</span>
                        <span>Nodes (Boîtiers)</span>
                    </a>
                </li>
                % end

                % if current_user.get('is_admin'):
                <li class="nav-group">
                    <span class="nav-label">
                        <span class="material-symbols-outlined icon-label">admin_panel_settings</span> Administration
                    </span>
                    <ul class="sub-nav">
                        <li>
                            <a href="{{BASE_PATH}}/maintenance/templates" class="{{'active' if '/maintenance/templates' in request_path else ''}}">
                                <span class="material-symbols-outlined">library_books</span> Templates Modbus
                            </a>
                        </li>
                        <li>
                            <a href="{{BASE_PATH}}/dev" class="{{'active' if request_path == BASE_PATH + '/dev' else ''}}">
                                <span class="material-symbols-outlined">terminal</span> Espace Dev
                            </a>
                        </li>
                    </ul>
                </li>
                % end
            </ul>
            
            <div style="margin-top: auto; padding: 20px; font-size: 0.7rem; color: var(--outline); text-align: center;">
                Deltathermic &copy; 2026<br>Infrastructure Reports
            </div>
        </nav>

        <main class="main-content" id="main-content">
            {{!base}}
        </main>
    </div>

    <script>
      // Service Worker (PWA)
      if ('serviceWorker' in navigator) {
        window.addEventListener('load', function() {
          navigator.serviceWorker.register('{{BASE_PATH}}/sw.js', { scope: '{{BASE_PATH}}/' });
        });
      }

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
                          dot.style.backgroundColor = 'var(--secondary)';
                          dot.style.boxShadow = 'var(--glow-secondary)';
                          setTimeout(() => {
                              dot.style.backgroundColor = 'var(--outline-variant)';
                              dot.style.boxShadow = 'none';
                          }, 800);
                      }
                  }
              } catch (e) {}
          };
      }
      initGlobalAppSSE();
    </script>
</body>
</html>
